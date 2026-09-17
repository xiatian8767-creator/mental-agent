from analysis.audio_analysis import AudioAnalysis
from analysis.text_analysis import TextAnalysis
from analysis.visual_analysis import VisualAnalysis
from input import Input
from judge.Judge_Agent import JudgeAgent


input_processor = Input(
    samples_path="data/samples/1.json",
    output_dir="data/analysis/",
)
input_processor.run()

analysis_path = "data/analysis/1.json"

text_agent = TextAnalysis(analysis_path=analysis_path)
text_agent.run()

visual_agent = VisualAnalysis(analysis_path=analysis_path)
visual_agent.run()

audio_agent = AudioAnalysis(analysis_path=analysis_path)
audio_agent.run()

judge_agent = JudgeAgent(
    analysis_path=analysis_path,
    prompt_path="judge/prompt",
)
judge_agent.run()
