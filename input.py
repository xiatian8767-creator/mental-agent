"""Input module for preparing multimodal samples for analysis agents."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


class Input:
    """Read, validate, and initialize the analysis JSON for one sample."""

    _INPUT_FIELDS = ("text", "image_path", "audio_path")

    def __init__(self, samples_path: str, output_dir: str):
        project_dir = Path(__file__).resolve().parent

        self.samples_path = Path(samples_path)
        if not self.samples_path.is_absolute():
            self.samples_path = project_dir / self.samples_path

        self.output_dir = Path(output_dir)
        if not self.output_dir.is_absolute():
            self.output_dir = project_dir / self.output_dir

    def read_sample(self) -> dict:
        """Read the source sample as UTF-8 JSON."""
        with self.samples_path.open("r", encoding="utf-8") as file:
            sample = json.load(file)

        if not isinstance(sample, dict):
            raise ValueError("The sample JSON root must be an object.")
        return sample

    def validate_sample(self, sample: dict) -> None:
        """Validate the input contract described by the Input module spec."""
        if not isinstance(sample, dict):
            raise ValueError("sample must be a dictionary.")

        if "sample_id" not in sample:
            raise ValueError("Missing required field: sample_id.")
        sample_id = sample["sample_id"]
        if isinstance(sample_id, bool) or not isinstance(sample_id, int):
            raise ValueError("sample_id must be an integer.")
        if sample_id < 1:
            raise ValueError("sample_id must start from 1.")

        if "input" not in sample:
            raise ValueError("Missing required field: input.")
        input_data = sample["input"]
        if not isinstance(input_data, dict):
            raise ValueError("input must be an object.")

        for field in self._INPUT_FIELDS:
            if field not in input_data:
                raise ValueError(f"Missing required field: input.{field}.")
            value = input_data[field]
            if value is not None and not isinstance(value, str):
                raise ValueError(f"input.{field} must be a string or null.")

        for field in ("image_path", "audio_path"):
            value = input_data[field]
            if value is not None and Path(value).is_absolute():
                raise ValueError(f"input.{field} must be a relative path or null.")

    def init_analysis(self, sample: dict) -> dict:
        """Create empty analysis slots only for modalities that are present."""
        self.validate_sample(sample)
        input_data = deepcopy(sample["input"])

        def empty_analysis() -> Dict[str, Any]:
            return {
                "description": None,
                "reasoning": None,
                "result": [],
            }

        return {
            "sample_id": sample["sample_id"],
            "input": input_data,
            "analysis": {
                "text": empty_analysis() if input_data["text"] is not None else None,
                "visual": (
                    empty_analysis() if input_data["image_path"] is not None else None
                ),
                "audio": (
                    empty_analysis() if input_data["audio_path"] is not None else None
                ),
            },
        }

    def write_analysis(self, data: dict) -> None:
        """Write the initialized analysis document as ``<sample_id>.json``."""
        sample_id = data.get("sample_id")
        if isinstance(sample_id, bool) or not isinstance(sample_id, int):
            raise ValueError("Analysis data must contain an integer sample_id.")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{sample_id}.json"
        with output_path.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def run(self) -> None:
        """Execute the complete input-to-analysis initialization flow."""
        sample = self.read_sample()
        self.validate_sample(sample)
        data = self.init_analysis(sample)
        self.write_analysis(data)
