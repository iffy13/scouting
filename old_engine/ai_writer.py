import os
import re
import json
import logging
import aiohttp
from typing import Dict, Any, Tuple, Optional
from config import SENDER_NAME

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

COUNTRY_LANGUAGES = {
    "DE": "German", "AT": "German", "CH": "German",
    "FR": "French", "BE": "French", "LU": "French", "MC": "French",
    "ES": "Spanish",
    "IT": "Italian",
    "PT": "Portuguese",
    "NL": "Dutch",
    "NO": "Norwegian", "SE": "Swedish", "DK": "Danish", "FI": "Finnish",
    "PL": "Polish", "CZ": "Czech", "RO": "Romanian", "GR": "Greek",
    "US": "English", "UK": "English", "CA": "English", "AU": "English",
    "NZ": "English", "IE": "English", "SG": "English", "HK": "English",
    "AE": "English", "SA": "English", "QA": "English", "KW": "English"
}

COUNTRY_NAMES = {
    "DE": "Germany", "AT": "Austria", "CH": "Switzerland",
    "FR": "France", "BE": "Belgium", "LU": "Luxembourg", "MC": "Monaco",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "NL": "Netherlands",
    "NO": "Norway", "SE": "Sweden", "DK": "Denmark", "FI": "Finland",
    "PL": "Poland", "CZ": "Czech Republic", "RO": "Romania", "GR": "Greece",
    "US": "the US", "UK": "the UK", "CA": "Canada", "AU": "Australia",
    "NZ": "New Zealand", "IE": "Ireland", "SG": "Singapore", "HK": "Hong Kong",
    "AE": "the UAE", "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait"
}

class DynamicAIWriter:
    """
    Generates deeply emotional, human, high-conversion cold emails in the prospect's native language.
    Speaks directly to business owners and authors with zero AI buzzwords, zero unnatural dashes,
    and crystal-clear problems, consequences, and solutions.
    """

    @staticmethod
    async def generate_email(
        business: Dict[str, Any],
        signals: Dict[str, Any],
        stage: int = 1,
        mockup_link: str = "https://demo.ai-voice.io/preview"
    ) -> Tuple[str, str]:
        biz_name = business.get("clean_name") or business.get("name", "your team")
        founder = business.get("founder_name") or business.get("first_name")
        
        country_code = (business.get("country") or "US").upper()
        country_full = COUNTRY_NAMES.get(country_code, country_code)
        country = country_full
        target_lang = COUNTRY_LANGUAGES.get(country_code, "English")
        
        raw_city = business.get("city")
        if raw_city and raw_city.lower() != "general" and len(raw_city) > 2 and raw_city.upper() != country_code:
            location = raw_city
        else:
            location = country_full
            
        # Filter junk or email fragments out of founder name
        generic_names = {"hello", "info", "contact", "support", "admin", "sales", "office", "team", "mail", "help"}
        if founder:
            f_clean = founder.lower().strip()
            if f_clean in generic_names or "." in f_clean or "@" in f_clean or len(f_clean) < 2 or re.search(r"\.support|\.com|\.net", f_clean):
                founder = None

        # Clean business name if it is an email or domain
        if biz_name and ("@" in biz_name or biz_name.lower().endswith(".com") or "." in biz_name):
            biz_name = biz_name.split("@")[-1].split(".")[0].capitalize()
        if not biz_name or biz_name.lower() in generic_names:
            biz_name = "your team"
        services = business.get("flagship_services", [])
        
        # Clean service description
        if services and len(services) > 0:
            services_str = services[0].lower()
        else:
            services_str = business.get("keyword", "services").lower()

        # Sanitize any accidental numbers or junk
        services_str = re.sub(r"[\d\(\)\-\+\:]+", "", services_str).strip()
        if len(services_str) < 3:
            services_str = business.get("keyword", "services").lower()

        research_summary = business.get("research_summary", "")
        background = business.get("company_background", "")
        biz_type = business.get("business_type", "local")

        has_youtube = signals.get("has_youtube", False)
        copyright_year = signals.get("copyright_year")

        # Select Offer Type
        if biz_type == "author" or "author" in business.get("keyword", "").lower() or "book" in business.get("keyword", "").lower():
            offer = "book_trailer"
        elif has_youtube or biz_type == "creator":
            offer = "video_clips"
        elif not business.get("website") or (copyright_year and copyright_year <= 2021):
            offer = "website"
        else:
            offer = "receptionist"

        # If Gemini API Key exists, generate with live LLM in target language
        if GEMINI_API_KEY:
            llm_result = await DynamicAIWriter._generate_with_gemini(
                biz_name=biz_name,
                founder=founder,
                location=location,
                country=country,
                target_lang=target_lang,
                services_str=services_str,
                background=background,
                research_summary=research_summary,
                offer=offer,
                stage=stage,
                mockup_link=mockup_link
            )
            if llm_result:
                return llm_result

        # Pure Human Copywriting Engine (with native language templates)
        return DynamicAIWriter._generate_pure_human_email(
            biz_name=biz_name,
            founder=founder,
            location=location,
            country=country,
            target_lang=target_lang,
            services_str=services_str,
            offer=offer,
            stage=stage,
            mockup_link=mockup_link
        )

    @staticmethod
    async def _generate_with_gemini(
        biz_name: str,
        founder: Optional[str],
        location: str,
        country: str,
        target_lang: str,
        services_str: str,
        background: str,
        research_summary: str,
        offer: str,
        stage: int,
        mockup_link: str
    ) -> Optional[Tuple[str, str]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        prompt = f"""
You are {SENDER_NAME}. Write a 100% human, emotional cold email to the owner of {biz_name} in {location} ({country}).
Recipient: {founder or 'The Team'}
Business Niche: {services_str}
Offer: {offer}
Stage: Stage {stage} of 6
Language Requirement: Write the entire email (both subject and body) in {target_lang}.

STRICT HUMAN WRITING RULES:
1. Write like a local person talking directly to another business owner or author in {target_lang}. Simple, honest, conversational.
2. Use authentic native greetings (e.g. 'Hallo {founder or biz_name}' for German; 'Bonjour {founder or biz_name}' for French; 'Hola {founder or biz_name}' for Spanish; 'Ciao {founder or biz_name}' for Italian; 'Olá {founder or biz_name}' for Portuguese).
3. Clearly explain the exact problem:
   - For Trades: Missed emergency calls going to voicemail while busy or asleep.
   - For Authors: Hard work writing a book, but missing out on BookTok / Instagram Reels video discovery.
   - For Creators: Spending hours filming long videos while audiences only watch 30s clips.
4. Clearly explain the painful consequence (lost jobs to competitors, lost book sales, low reach).
5. Clearly explain what we do and the tangible benefit.
6. NO AI WORDS. STRICTLY BANNED: "tailored", "leverage", "delve", "streamline", "bottleneck", "seamless", "cutting-edge", "game changer", "vital", "testament", "craftsmanship", "digital front door".
7. NO DASHES. Do NOT use em-dashes (—) or double hyphens (--). Use normal punctuation only.
8. NO LINKS OR PORTFOLIOS AT ALL in any email stages. Never send a URL or portfolio link. Keep it strictly conversational, offering to send a sample/audio clip only if they reply.
9. Return strictly JSON: {{"subject": "...", "body": "..."}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "response_mime_type": "application/json"}
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text)
                        return parsed.get("subject"), parsed.get("body")
        except Exception as e:
            logger.warning(f"Gemini generation error: {e}")
        return None

    @staticmethod
    def _generate_pure_human_email(
        biz_name: str,
        founder: Optional[str],
        location: str,
        country: str = "US",
        target_lang: str = "English",
        services_str: str = "services",
        offer: str = "receptionist",
        stage: int = 1,
        mockup_link: str = ""
    ) -> Tuple[str, str]:
        generic_names = {"hello", "info", "contact", "support", "admin", "sales", "office", "team", "mail", "help"}
        if founder and founder.lower().strip() in generic_names:
            founder = None

        # Localized Greetings
        if target_lang == "German":
            greeting = f"Hallo {founder}," if founder else f"Hallo {biz_name}-Team,"
        elif target_lang == "French":
            greeting = f"Bonjour {founder}," if founder else f"Bonjour l'équipe {biz_name},"
        elif target_lang == "Spanish":
            greeting = f"Hola {founder}," if founder else f"Hola equipo de {biz_name},"
        elif target_lang == "Italian":
            greeting = f"Ciao {founder}," if founder else f"Ciao al team di {biz_name},"
        elif target_lang == "Portuguese":
            greeting = f"Olá {founder}," if founder else f"Olá equipa {biz_name},"
        elif target_lang == "Dutch":
            greeting = f"Beste {founder}," if founder else f"Beste team {biz_name},"
        else:
            greeting = f"Hi {founder}," if founder else f"Hi {biz_name} team,"

        loc_text = f" in {location}" if location else ""

        if offer == "receptionist":
            if target_lang == "German":
                if stage == 1:
                    subject = f"Verpasste Anrufe bei {biz_name}"
                    body = f"{greeting}\n\nIch habe mir Ihr Unternehmen online angesehen. Wenn Ihr Team unterwegs oder auf Baustellen ist, ist es unmöglich, jeden Anruf sofort entgegenzunehmen.\n\nKunden rufen bei Notfällen oft den nächsten Betrieb an, anstatt auf die Mailbox zu sprechen. Unser KI-Telefonassistent nimmt Anrufe rund um die Uhr sofort an, beantwortet Kundenfragen und bucht Termine direkt in Ihren Kalender.\n\nDarf ich Ihnen eine kurze 1-minütige Hörprobe senden, wie das für Ihr Unternehmen klingt?\n\n{SENDER_NAME}"
                else:
                    subject = f"Re: Hörprobe Telefonassistent für {biz_name}"
                    body = f"{greeting}\n\nIch wollte mich kurz erkundigen, ob Sie mein vorheriges Schreiben gesehen haben.\n\nIch habe eine kurze 1-minütige Hörprobe vorbereitet, die zeigt, wie der Telefonassistent Notfachanrufe für Ihr Unternehmen entgegennimmt.\n\nLassen Sie mich einfach wissen, ob ich Ihnen die Aufnahme zusenden darf.\n\n{SENDER_NAME}"
                return subject, body
            elif target_lang == "French":
                if stage == 1:
                    subject = f"Appels manqués chez {biz_name}"
                    body = f"{greeting}\n\nJ'ai découvert votre entreprise en ligne. Quand votre équipe est en intervention, il est difficile de répondre à chaque appel téléphonique.\n\nLes clients qui tombent sur un répondeur appellent souvent directement un concurrent. Notre assistant téléphonique IA répond 24h/24 et 7j/7, prend les coordonnées et réserve les rendez-vous directement dans votre planning.\n\nPuis-je vous envoyer un court enregistrement démo d'une minute montrant comment il répond pour votre entreprise ?\n\n{SENDER_NAME}"
                else:
                    subject = f"Re: Démo assistant téléphonique pour {biz_name}"
                    body = f"{greeting}\n\nJe me permets de faire un bref suivi de mon précédent message.\n\nJ'ai enregistré un court exemple montrant comment l'assistant répond aux appels d'urgence pour {biz_name}.\n\nFaites-moi savoir si vous souhaitez que je vous l'envoie.\n\n{SENDER_NAME}"
                return subject, body
            elif target_lang == "Spanish":
                if stage == 1:
                    subject = f"Llamadas perdidas en {biz_name}"
                    body = f"{greeting}\n\nEstuve revisando su negocio online. Cuando su equipo está trabajando o en ruta, es imposible atender cada llamada entrante.\n\nLos clientes con urgencias rara vez dejan un mensaje de voz; cuelgan y llaman a la competencia. Nuestro asistente telefónico con IA atiende 24/7 al primer tono, toma los datos del cliente y agenda el servicio directamente.\n\n¿Le puedo enviar un breve audio de 1 minuto mostrando cómo atiende las llamadas para su negocio?\n\n{SENDER_NAME}"
                else:
                    subject = f"Re: Demo de audio para {biz_name}"
                    body = f"{greeting}\n\nLe escribo brevemente para dar seguimiento a mi nota anterior.\n\nPreparé un breve audio de 1 minuto que muestra cómo el asistente contesta llamadas de emergencia para su negocio.\n\nAvíseme si le gustaría que se lo comparta.\n\n{SENDER_NAME}"
                return subject, body

        if offer == "book_trailer":
            if stage == 1:
                subject = f"quick question about your book reach"
                body = (
                    f"{greeting}\n\n"
                    f"I was looking at your work online and saw your books. You have great reader reviews, but I wanted to point out something that might help your sales.\n\n"
                    f"I know how much time, research, and energy goes into writing a book. The frustrating part today is that traditional book promotion simply does not work like it used to. Most readers now discover their next read on TikTok (BookTok) and Instagram Reels through quick 15-second cinematic book trailers and 3D teasers.\n\n"
                    f"Without short cinematic videos, over 80% of readers scrolling on their phones will never know your book exists.\n\n"
                    f"We take your book cover and story themes and turn them into 3D animated cinematic book trailers and viral vertical teaser clips designed to make readers stop scrolling and buy on Amazon.\n\n"
                    f"I put together a quick 20-second sample cinematic trailer showing how a BookTok teaser looks for your book. Can I send that sample over for you to see?\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"Re: sample book trailer for {biz_name}"
                body = (
                    f"{greeting}\n\n"
                    f"Following up briefly on my note from earlier. I put together a quick 20-second cinematic video hook designed for your books on TikTok and Reels.\n\n"
                    f"Let me know if you would like me to send it over for you to check out.\n\n"
                    f"{SENDER_NAME}"
                )
        elif offer == "receptionist":
            if stage == 1:
                subject = f"missed calls when you are on a job in {location}" if location else f"missed customer calls when you are on a job"
                body = (
                    f"{greeting}\n\n"
                    f"I was looking at your business online{loc_text}. You have a great reputation, but I know how hectic running {services_str} jobs can get.\n\n"
                    f"When your team is out on a site or driving, picking up every single incoming phone call is impossible. The problem is, when a customer has an urgent issue or wants to book a job at 7 PM, they never leave a voicemail. They hang up in three seconds and call the next company on Google. That is an easy $1,000 to $2,500 repair job handed straight to your competitor.\n\n"
                    f"We set up a 24/7 AI phone assistant that answers on the first ring every time. It talks to the customer naturally, asks what is broken, gets their address, and books the job right into your schedule while sending you a text with the details.\n\n"
                    f"This means you capture every after-hours and emergency job without paying for extra office staff or having to stay glued to your phone all evening.\n\n"
                    f"I put together a quick 1-minute audio recording showing how it answers an emergency call and takes down the details for your business. Can I send the audio clip over for you to hear it?\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"Re: missed calls for {biz_name}"
                body = (
                    f"{greeting}\n\n"
                    f"Following up briefly on my previous note. I put together a short 1-minute audio recording demonstrating how the phone assistant answers an emergency call and books the customer for {biz_name}.\n\n"
                    f"Let me know if you would like me to send the clip over for you to hear.\n\n"
                    f"{SENDER_NAME}"
                )
        elif offer == "video_clips":
            if stage == 1:
                subject = f"getting more reach from your videos"
                body = (
                    f"{greeting}\n\n"
                    f"I was watching some of your content online{loc_text}. You share really valuable insights, but I noticed a big opportunity to get 5x to 10x more reach from the videos you already have.\n\n"
                    f"Long videos take hours to produce, but most people scrolling on mobile only consume 30 to 60-second vertical reels on TikTok, YouTube Shorts, and Instagram.\n\n"
                    f"We take your existing long videos and turn them into high-retention short clips with dynamic subtitles, sound design, and viral hooks designed to drive traffic and new clients.\n\n"
                    f"I edited a quick sample clip from your content to show you what it looks like. Can I send that sample over?\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"Re: sample video clips for {biz_name}"
                body = (
                    f"{greeting}\n\n"
                    f"Checking in briefly regarding my earlier note. I have that sample vertical video clip ready for you to preview.\n\n"
                    f"Let me know if you would like me to pass it over.\n\n"
                    f"{SENDER_NAME}"
                )
        else: # website / booking funnel
            if stage == 1:
                subject = f"quick question about your website booking flow"
                body = (
                    f"{greeting}\n\n"
                    f"I was looking at your {services_str} work online{loc_text}. The quality of your work is clear, but I wanted to point out a quick issue with your website on phones.\n\n"
                    f"When customers search for you on their mobile phones after work, any slow loading or confusing layout makes them leave immediately. Most people will not spend time pinching their screen to find a contact form. They click back to Google and hire the next business that has a simple one-tap booking button.\n\n"
                    f"We build clean, modern mobile pages that let customers tap one button on their phone to request a quote or book your team in ten seconds.\n\n"
                    f"This stops people from bouncing off your site and turns regular website visitors into booked jobs every week.\n\n"
                    f"I built a quick preview showing what this simplified booking page looks like for {biz_name}. Would you be open to taking a look? It is completely free either way.\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"Re: mobile booking preview for {biz_name}"
                body = (
                    f"{greeting}\n\n"
                    f"Following up briefly on my earlier note about {biz_name}. I have the clean mobile booking preview ready if you would like to take a look.\n\n"
                    f"Let me know if you'd like me to send it over.\n\n"
                    f"{SENDER_NAME}"
                )

        return subject, body
