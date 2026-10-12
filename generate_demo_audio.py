import asyncio
import edge_tts
import os
import base64

VOICE_AI = "en-AU-NatashaNeural"
VOICE_CALLER = "en-AU-WilliamNeural"

dialogue = [
    (VOICE_AI, "Thanks for calling Melbourne 24/7 Rapid Response. My name is Natasha. Are you calling with an urgent booking or emergency?"),
    (VOICE_CALLER, "Hi, yeah! Our commercial air conditioning unit just tripped the main switchboard here in South Melbourne, and we need an emergency technician out as soon as possible."),
    (VOICE_AI, "Got it. First, please ensure the main sub-board is switched off for safety. What is your exact property address in South Melbourne so I can route our nearest on-call technician?"),
    (VOICE_CALLER, "It's 42 Clarendon Street, South Melbourne."),
    (VOICE_AI, "Understood. Our after-hours emergency call-out fee is one hundred and eighty dollars, which gets applied directly toward your repair. We have a certified technician nearby who can arrive within 40 minutes. May I grab your name and mobile number for dispatch updates?"),
    (VOICE_CALLER, "Yes, absolutely. Name is David, mobile is 0418 293 841."),
    (VOICE_AI, "Perfect, David. Technician Liam has been dispatched to 42 Clarendon Street. I've just sent a confirmation SMS to your mobile with his live ETA. Help is on the way.")
]

async def generate():
    temp_files = []
    print("Generating neural Australian audio segments...")
    for i, (voice, text) in enumerate(dialogue):
        fname = f"temp_segment_{i}.mp3"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(fname)
        temp_files.append(fname)
        print(f"Segment {i+1}/{len(dialogue)} generated.")

    # Combine binary MP3 segments
    combined_mp3_path = "melbourne_ai_call_sample.mp3"
    with open(combined_mp3_path, "wb") as outfile:
        for fname in temp_files:
            with open(fname, "rb") as infile:
                outfile.write(infile.read())
            # Clean up temp
            try:
                os.remove(fname)
            except:
                pass

    print(f"Combined MP3 created: {combined_mp3_path} ({os.path.getsize(combined_mp3_path)} bytes)")
    
    # Also encode to base64
    with open(combined_mp3_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
        
    print(f"Base64 length: {len(b64)}")
    return combined_mp3_path, b64

if __name__ == "__main__":
    asyncio.run(generate())
