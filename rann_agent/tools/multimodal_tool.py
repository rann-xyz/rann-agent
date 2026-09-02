"""
Multimodal tools - vision, voice, video.
"""

from typing import Dict, Any
from ..multimodal.vision import VisionSystem
from ..multimodal.voice import VoiceSystem


class MultimodalTool:
    """Vision and voice capabilities."""
    
    name = "multimodal"
    description = "Vision (OCR, image analysis) and Voice (TTS, STT)"
    
    def __init__(self):
        self.vision = VisionSystem()
        self.voice = VoiceSystem()
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute multimodal operations.
        
        Actions:
            - ocr: Extract text from image
            - analyze_screenshot: Analyze screenshot
            - text_to_speech: Convert text to speech
            - speech_to_text: Convert speech to text
        """
        if action == "ocr":
            image_path = kwargs.get("image_path", "")
            result = await self.vision.ocr(image_path)
            return result
        
        elif action == "analyze_screenshot":
            image_path = kwargs.get("image_path", "")
            result = await self.vision.analyze_screenshot(image_path)
            return {"success": True, "analysis": result}
        
        elif action == "text_to_speech":
            text = kwargs.get("text", "")
            output_file = kwargs.get("output_file", "output.mp3")
            voice = kwargs.get("voice", "en")
            
            result = await self.voice.text_to_speech(text, output_file, voice)
            return {"success": True, "audio_file": result}
        
        elif action == "speech_to_text":
            audio_file = kwargs.get("audio_file", "")
            text = await self.voice.speech_to_text(audio_file)
            return {"success": True, "text": text}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
