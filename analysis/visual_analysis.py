"""Visual modality analysis agent."""

import base64
import json
import mimetypes
from pathlib import Path
from string import Template
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class VisualAnalysis:
    def __init__(self, analysis_path: str):
        self.project_dir = Path(__file__).resolve().parents[1]
        self.analysis_path = Path(analysis_path)
        if not self.analysis_path.is_absolute():
            self.analysis_path = self.project_dir / self.analysis_path
        self.prompt_path = Path(__file__).with_name("prompt.json")
        self.env_path = self.project_dir / ".env"

    def read_analysis(self) -> dict:
        with self.analysis_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def read_prompt(self) -> dict:
        with self.prompt_path.open("r", encoding="utf-8") as file:
            return json.load(file)["visual"]

    def read_api_config(self) -> dict:
        config = self._read_env()
        required = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_VISUAL_MODEL")
        missing = [key for key in required if not config.get(key)]
        if missing:
            raise ValueError(f".env 缺少配置：{', '.join(missing)}")
        return {
            "api_key": config["OPENAI_API_KEY"],
            "base_url": config["OPENAI_BASE_URL"],
            "visual_model": config["OPENAI_VISUAL_MODEL"],
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

    def read_image(self, image_path: str) -> tuple[str, str]:
        path = Path(image_path)
        if not path.is_absolute():
            path = self.project_dir / path
        if not path.is_file():
            raise FileNotFoundError(f"图片文件不存在：{path}")

        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        image_data = base64.b64encode(path.read_bytes()).decode("ascii")
        return mime_type, image_data

    def call_api(self, prompt: str, image_path: str) -> dict:
        config = self.read_api_config()
        mime_type, image_data = self.read_image(image_path)
        payload = {
            "model": config["visual_model"],
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{image_data}",
                        },
                    ],
                }
            ],
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        response = self._post_api(config, "/responses", payload)

        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return self._parse_json(content.get("text", ""))
        raise ValueError("API 没有返回文本结果。")

    def write_analysis(self, data: dict) -> None:
        with self.analysis_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def run(self) -> None:
        data = self.read_analysis()
        image_path = data["input"]["image_path"]

        if image_path is None:
            return
        if not isinstance(data["analysis"]["visual"], dict):
            raise ValueError("analysis.visual 必须是对象。")

        prompts = self.read_prompt()
        first_result = self.call_api(prompts["analysis_prompt"], image_path)
        description, reasoning = self._read_description_reasoning(first_result)

        data["analysis"]["visual"]["description"] = description
        data["analysis"]["visual"]["reasoning"] = reasoning
        self.write_analysis(data)

        result_prompt = Template(prompts["result_prompt"]).substitute(
            description=description,
            reasoning=reasoning,
        )
        second_result = self.call_api(result_prompt, image_path)
        result = self._read_result(second_result)

        data["analysis"]["visual"]["result"] = result
        self.write_analysis(data)

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

    @staticmethod
    def _read_description_reasoning(result: dict) -> tuple[str, str]:
        description = result.get("description")
        reasoning = result.get("reasoning")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description 必须是非空字符串。")
        if not isinstance(reasoning, str) or not reasoning.strip():
            raise ValueError("reasoning 必须是非空字符串。")
        return description, reasoning

    @staticmethod
    def _read_result(result: dict) -> list[str]:
        emotions = result.get("result")
        if not isinstance(emotions, list) or not 1 <= len(emotions) <= 3:
            raise ValueError("result 必须包含一至三个情感词。")
        if any(not isinstance(item, str) or not item.strip() for item in emotions):
            raise ValueError("result 中的情感词必须是非空字符串。")
        return emotions
