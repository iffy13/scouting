import base64

def update_html():
    mp3_path = "melbourne_ai_call_sample.mp3"
    with open(mp3_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    whatsapp_number = "447853164638"
    prefilled_msg = "Hi Akdam, I just listened to the 24/7 AI Receptionist demo call and I would like to see how this works for our business."
    import urllib.parse
    encoded_msg = urllib.parse.quote(prefilled_msg)
    wa_url = f"https://wa.me/{whatsapp_number}?text={encoded_msg}"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>24/7 AI Receptionist Demo | Live Call Simulation</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #111827;
            --accent: #3b82f6;
            --accent-green: #10b981;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #1f2937;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: var(--bg-color); color: var(--text-main); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 24px 16px; }}
        .container {{ max-width: 620px; width: 100%; background: var(--card-bg); border-radius: 20px; padding: 32px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); border: 1px solid var(--border); }}
        .header {{ text-align: center; margin-bottom: 24px; }}
        .badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(16, 185, 129, 0.12); color: var(--accent-green); font-size: 12px; font-weight: 600; padding: 4px 14px; border-radius: 9999px; margin-bottom: 12px; border: 1px solid rgba(16, 185, 129, 0.3); text-transform: uppercase; letter-spacing: 0.5px; }}
        .pulse-dot {{ width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); animation: blink 1.5s infinite; }}
        @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
        h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #fff; letter-spacing: -0.5px; }}
        p.subtitle {{ font-size: 14px; color: var(--text-muted); line-height: 1.5; max-width: 500px; margin: 0 auto; }}
        
        .player-card {{ background: #080d1a; border-radius: 14px; padding: 20px; margin: 24px 0; border: 1px solid #1e293b; }}
        .call-meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--text-muted); margin-bottom: 16px; border-bottom: 1px solid #1e293b; padding-bottom: 10px; }}
        .call-meta span.live {{ color: #38bdf8; font-weight: 600; }}
        .audio-controls {{ display: flex; align-items: center; justify-content: center; gap: 16px; }}
        .play-btn {{ background: #2563eb; color: white; border: none; width: 54px; height: 54px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 20px; transition: all 0.2s; box-shadow: 0 0 15px rgba(37, 99, 235, 0.4); }}
        .play-btn:hover {{ background: #1d4ed8; transform: scale(1.05); }}
        .wave-container {{ flex: 1; height: 40px; display: flex; align-items: center; justify-content: center; gap: 4px; padding: 0 10px; }}
        .bar {{ width: 4px; height: 8px; background: #334155; border-radius: 3px; transition: height 0.15s ease; }}
        .playing .bar {{ animation: pulse 0.8s infinite ease-in-out alternate; }}
        .playing .bar:nth-child(2) {{ animation-delay: 0.1s; }}
        .playing .bar:nth-child(3) {{ animation-delay: 0.2s; }}
        .playing .bar:nth-child(4) {{ animation-delay: 0.3s; }}
        .playing .bar:nth-child(5) {{ animation-delay: 0.4s; }}
        .playing .bar:nth-child(6) {{ animation-delay: 0.15s; }}
        .playing .bar:nth-child(7) {{ animation-delay: 0.35s; }}
        .playing .bar:nth-child(8) {{ animation-delay: 0.25s; }}
        @keyframes pulse {{ 0% {{ height: 6px; background: #3b82f6; }} 100% {{ height: 32px; background: #38bdf8; }} }}
        .time-badge {{ font-size: 13px; color: var(--text-muted); font-family: monospace; min-width: 80px; text-align: right; }}

        .transcript-box {{ background: #080d1a; border-radius: 14px; padding: 18px; margin-bottom: 20px; max-height: 260px; overflow-y: auto; border: 1px solid #1e293b; font-size: 13px; line-height: 1.6; }}
        .msg {{ margin-bottom: 14px; display: flex; flex-direction: column; }}
        .msg.caller .speaker {{ color: #f59e0b; font-weight: 600; font-size: 11px; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .msg.ai .speaker {{ color: var(--accent-green); font-weight: 600; font-size: 11px; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .msg .text {{ background: rgba(255, 255, 255, 0.03); padding: 10px 14px; border-radius: 10px; border-left: 3px solid #334155; }}
        .msg.ai .text {{ border-left-color: var(--accent-green); }}
        .msg.caller .text {{ border-left-color: #f59e0b; }}

        .sms-box {{ background: rgba(6, 78, 59, 0.3); border: 1px solid #059669; border-radius: 12px; padding: 16px; margin-bottom: 24px; font-size: 12px; }}
        .sms-title {{ color: var(--accent-green); font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; font-size: 13px; }}
        .sms-body {{ color: #d1fae5; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; line-height: 1.5; }}

        .cta-box {{ text-align: center; }}
        .cta-btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 10px; background: #25D366; color: #ffffff; font-weight: 700; text-decoration: none; padding: 15px 30px; border-radius: 12px; font-size: 15px; transition: all 0.2s; box-shadow: 0 4px 15px rgba(37, 211, 102, 0.35); }}
        .cta-btn:hover {{ background: #20ba59; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(37, 211, 102, 0.5); }}
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <div class="badge"><div class="pulse-dot"></div> Live Call Simulation</div>
        <h1>24/7 AI Receptionist & Dispatcher</h1>
        <p class="subtitle">Listen to how the AI assistant answers on the first ring, qualifies the caller, captures address & contact details, and dispatches the booking instantly.</p>
    </div>

    <div class="player-card">
        <div class="call-meta">
            <span>Incoming Call: <strong style="color:#fff;">Melbourne, VIC</strong></span>
            <span class="live">● Ring 1 Pickup</span>
        </div>
        <div class="audio-controls">
            <button class="play-btn" id="playBtn" onclick="toggleAudio()">▶</button>
            <div class="wave-container" id="wave">
                <div class="bar"></div><div class="bar"></div><div class="bar"></div>
                <div class="bar"></div><div class="bar"></div><div class="bar"></div>
                <div class="bar"></div><div class="bar"></div>
            </div>
            <span id="timeDisplay" class="time-badge">0:00 / 0:34</span>
        </div>
        <audio id="demoAudio" preload="auto">
            <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        </audio>
    </div>

    <div class="transcript-box">
        <div class="msg ai">
            <span class="speaker">AI Assistant (Ring 1)</span>
            <span class="text">"Thanks for calling Melbourne 24/7 Rapid Response. My name is Natasha. Are you calling with an urgent booking or emergency?"</span>
        </div>
        <div class="msg caller">
            <span class="speaker">Caller (David)</span>
            <span class="text">"Hi, yeah! Our commercial air conditioning unit just tripped the main switchboard here in South Melbourne, and we need an emergency technician out as soon as possible."</span>
        </div>
        <div class="msg ai">
            <span class="speaker">AI Assistant</span>
            <span class="text">"Got it. First, please ensure the main sub-board is switched off for safety. What is your exact property address in South Melbourne so I can route our nearest on-call technician?"</span>
        </div>
        <div class="msg caller">
            <span class="speaker">Caller (David)</span>
            <span class="text">"It's 42 Clarendon Street, South Melbourne."</span>
        </div>
        <div class="msg ai">
            <span class="speaker">AI Assistant</span>
            <span class="text">"Understood. Our after-hours emergency call-out fee is $180 AUD, which gets applied directly toward your repair. We have a certified technician nearby who can arrive within 40 minutes. May I grab your name and mobile number for dispatch updates?"</span>
        </div>
        <div class="msg caller">
            <span class="speaker">Caller (David)</span>
            <span class="text">"Yes, absolutely. Name is David, mobile is 0418 293 841."</span>
        </div>
        <div class="msg ai">
            <span class="speaker">AI Assistant</span>
            <span class="text">"Perfect, David. Technician Liam has been dispatched to 42 Clarendon Street. I've just sent a confirmation SMS to your mobile with his live ETA. Help is on the way."</span>
        </div>
    </div>

    <div class="sms-box">
        <div class="sms-title">📱 INSTANT DISPATCH NOTIFICATION SENT TO BUSINESS OWNER:</div>
        <div class="sms-body">
            [NEW EMERGENCY DISPATCH]<br>
            • Client: David (0418 293 841)<br>
            • Location: 42 Clarendon St, South Melbourne VIC<br>
            • Issue: Commercial AC tripped main switchboard<br>
            • Fee Quoted: $180 AUD (Emergency Callout)<br>
            • Assigned Tech: Liam (ETA 40 mins)
        </div>
    </div>

    <div class="cta-box">
        <a href="{wa_url}" target="_blank" class="cta-btn">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946.003-6.556 5.338-11.891 11.893-11.891 3.181.001 6.167 1.24 8.413 3.488 2.245 2.248 3.481 5.236 3.48 8.414-.003 6.557-5.338 11.892-11.893 11.892-1.99-.001-3.951-.5-5.688-1.448l-6.305 1.654zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884-.001 2.225.651 3.891 1.746 5.634l-.999 3.648 3.742-.981zm11.387-5.464c-.074-.124-.272-.198-.57-.347-.297-.149-1.758-.868-2.031-.967-.272-.099-.47-.149-.669.149-.198.297-.768.967-.941 1.165-.173.198-.347.223-.644.074-.297-.149-1.255-.462-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.521.151-.172.2-.296.3-.495.099-.198.05-.372-.025-.521-.075-.148-.669-1.611-.916-2.206-.242-.579-.487-.501-.669-.51l-.57-.01c-.198 0-.52.074-.792.372s-1.04 1.016-1.04 2.479 1.065 2.876 1.213 3.074c.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.695.248-1.29.173-1.414z"/></svg>
            Chat On WhatsApp To Set This Up For Your Business →
        </a>
    </div>
</div>

<script>
    const audio = document.getElementById('demoAudio');
    const playBtn = document.getElementById('playBtn');
    const wave = document.getElementById('wave');
    const timeDisplay = document.getElementById('timeDisplay');

    function formatTime(seconds) {{
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return mins + ':' + (secs < 10 ? '0' : '') + secs;
    }}

    function toggleAudio() {{
        if (audio.paused) {{
            audio.play();
        }} else {{
            audio.pause();
        }}
    }}

    audio.addEventListener('play', () => {{
        playBtn.innerText = '⏸';
        wave.classList.add('playing');
    }});

    audio.addEventListener('pause', () => {{
        playBtn.innerText = '▶';
        wave.classList.remove('playing');
    }});

    audio.addEventListener('ended', () => {{
        playBtn.innerText = '▶';
        wave.classList.remove('playing');
    }});

    audio.addEventListener('timeupdate', () => {{
        const current = formatTime(audio.currentTime);
        const duration = formatTime(audio.duration || 34);
        timeDisplay.innerText = current + ' / ' + duration;
    }});
</script>

</body>
</html>
"""
    with open("demo_call.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("demo_call.html successfully updated with WhatsApp button!")

if __name__ == "__main__":
    update_html()
