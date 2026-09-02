"""
Voice capabilities - Text-to-Speech and Speech-to-Text.
"""

from typing import Optional
import subprocess


class VoiceSystem:
    """
    TTS and STT capabilities.
    """
    
    async def text_to_speech(
        self,
        text: str,
        output_file: str = "output.mp3",
        voice: str = "en"
    ) -> str:
        """Convert text to speech."""
        try:
            # Use gTTS (Google Text-to-Speech)
            from gtts import gTTS
            
            tts = gTTS(text=text, lang=voice)
            tts.save(output_file)
            
            return output_file
        except ImportError:
            return "Install: pip install gtts"
        except Exception as e:
            return f"Error: {e}"
    
    async def speech_to_text(self, audio_file: str) -> str:
        """Convert speech to text."""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(audio_file) as source:
                audio = recognizer.record(source)
            
            text = recognizer.recognize_google(audio)
            return text
        except ImportError:
            return "Install: pip install SpeechRecognition"
        except Exception as e:
            return f"Error: {e}"
