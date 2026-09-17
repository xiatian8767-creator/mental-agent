"""Judge agent for combining multimodal analysis results."""

import json
from pathlib import Path
from string import Template
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class JudgeAgent:
    def __init__(
        self,
        analysis_path: str,
        prompt_path: str,
        use_memory: bool = False,
    ):
        self.project_dir = Path(__file__).resolve().parents[1]
        self.use_memory = use_memory

        self.analysis_path = Path(analysis_path)
        if not self.analysis_path.is_absolute():
            self.analysis_path = self.project_dir / self.analysis_path

        self.prompt_path = Path(prompt_path)
        if not self.prompt_path.is_absolute():
            self.prompt_path = self.project_dir / self.prompt_path

        self.output_dir = self.project_dir / "data" / "judge"
        self.env_path = self.project_dir / ".env"

    def read_analysis(self) -> dict:
        with self.analysis_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("分析文件的根节点必须是 JSON 对象。")
        return data

    def read_prompt(self) -> str:
        with self.prompt_path.open("r", encoding="utf-8") as file:
            prompts = json.load(file)
        normal_prompt = prompts.get("normal_prompt")
        if not isinstance(normal_prompt, str) or not normal_prompt.strip():
            raise ValueError("judge/prompt 缺少有效的 normal_prompt。")
        return normal_prompt

    def read_api_config(self) -> dict:
        config = self._read_env()
        required = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_TEXT_MODEL")
        missing = [key for key in required if not config.get(key)]
        if missing:
            raise ValueError(f".env 缺少配置：{', '.join(missing)}")
        return {
            "api_key": config["OPENAI_API_KEY"],
            "base_url": config["OPENAI_BASE_URL"],
            "judge_model": config["OPENAI_TEXT_MODEL"],
        }

    def _read_env(self) -> dict:
        config = {}
        with self.env_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip().strip("\"'")
        return config

    def call_api(self, prompt: str) -> dict:
        config = self.read_api_config()
        payload = {
            "model": config["judge_model"],
            "input": prompt,
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        response = self._post_api(config, "/responses", payload)

        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return self._parse_json(content.get("text", ""))
        raise ValueError("API 没有返回文本结果。")

    def write_judge(self, data: dict) -> None:
        sample_id = data.get("sample_id")
        if isinstance(sample_id, bool) or not isinstance(sample_id, int):
            raise ValueError("sample_id 必须是整数。")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{sample_id}.json"
        with output_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def run(self) -> None:
        if self.use_memory:
            raise NotImplementedError("当前版本尚未开发 Memory Agent 讨论流程。")

        data = self.read_analysis()
        analysis = data.get("analysis")
        if not isinstance(analysis, dict):
            raise ValueError("analysis 必须是对象。")

        self._validate_analysis(analysis)
        prompt = Template(self.read_prompt()).substitute(
            analysis=json.dumps(analysis, ensure_ascii=False, indent=2)
        )
        result = self.call_api(prompt)
        judge = self._read_judge_result(result, analysis)

        data["judge"] = judge
        self.write_judge(data)

    @staticmethod
    def _validate_analysis(analysis: dict) -> None:
        available_count = 0
        for modality in ("text", "visual", "audio"):
            value = analysis.get(modality)
            if value is None:
                continue
            available_count += 1
            if not isinstance(value, dict):
                raise ValueError(f"analysis.{modality} 必须是对象或 null。")

            description = value.get("description")
            reasoning = value.get("reasoning")
            emotions = value.get("result")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"analysis.{modality}.description 尚未生成。")
            if not isinstance(reasoning, str) or not reasoning.strip():
                raise ValueError(f"analysis.{modality}.reasoning 尚未生成。")
            if not isinstance(emotions, list) or not emotions:
                raise ValueError(f"analysis.{modality}.result 尚未生成。")

        if available_count == 0:
            raise ValueError("至少需要一个已经完成的模态分析结果。")

    @staticmethod
    def _read_judge_result(result: dict, analysis: dict) -> dict:
        thinking = result.get("thinking")
        if not isinstance(thinking, str) or not thinking.strip():
            raise ValueError("thinking 必须是非空字符串。")

        score_fields = {
            "txt_score": "text",
            "visual_score": "visual",
            "audio_score": "audio",
        }
        scores = {}
        for field, modality in score_fields.items():
            score = result.get(field)
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValueError(f"{field} 必须是数字。")
            score = float(score)
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"{field} 必须在 0 到 1 之间。")
            if analysis.get(modality) is None and score != 0.0:
                raise ValueError(f"缺失模态 {modality} 的权重必须为 0。")
            scores[field] = score

        if abs(sum(scores.values()) - 1.0) > 1e-6:
            raise ValueError("txt_score、visual_score 和 audio_score 的总和必须为 1。")

        final_result = result.get("final_result")
        if not isinstance(final_result, list) or not 1 <= len(final_result) <= 3:
            raise ValueError("final_result 必须包含一至三个情感词。")
        if any(
            not isinstance(item, str) or not item.strip() for item in final_result
        ):
            raise ValueError("final_result 中的情感词必须是非空字符串。")

        return {
            "thinking": thinking.strip(),
            "memory_advise": "",
            "txt_score": scores["txt_score"],
            "visual_score": scores["visual_score"],
            "audio_score": scores["audio_score"],
            "final_result": [item.strip() for item in final_result],
        }

    @staticmethod
    def _post_api(config: dict, endpoint: str, payload: dict) -> dict:
        url = config["base_url"].rstrip("/") + endpoint
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API 请求失败（{error.code}）：{detail}") from error

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        result = json.loads(text.strip())
        if not isinstance(result, dict):
            raise ValueError("API 返回结果必须是 JSON 对象。")
        return result
