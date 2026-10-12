import logging
from typing import Dict, Any, Tuple
from config import SENDER_NAME

logger = logging.getLogger(__name__)

class OfferRuleEngine:
    """Matches business signals to the ideal offer and builds personalized sequence copy."""

    @staticmethod
    def determine_offer(business: Dict[str, Any], signals: Dict[str, Any]) -> str:
        """
        Rule engine to pick the optimal offer:
        1. 'video_clips': If has YouTube/active video content or is a creator/podcast.
        2. 'website': If no website or site is outdated (copyright <= 2021).
        3. 'receptionist': If has a live website, phone number, but no online booking/chat.
        4. 'ai_automation': If tech/digital/AI business.
        """
        b_type = business.get("business_type", "local")
        has_website = bool(business.get("website"))
        has_youtube = signals.get("has_youtube", False)
        has_booking_chat = signals.get("has_booking_chat", False)
        copyright_year = signals.get("copyright_year")

        if b_type == "creator" or has_youtube:
            return "video_clips"

        if not has_website or (copyright_year and copyright_year <= 2021):
            return "website"

        if has_website and not has_booking_chat:
            return "receptionist"

        if b_type in ("digital", "ai_tech"):
            return "ai_automation"

        return "website"

    @staticmethod
    def get_email_copy(
        offer_type: str,
        stage: int,
        business: Dict[str, Any],
        first_name: str = "there",
        mockup_link: str = "https://your-portfolio.com/preview"
    ) -> Tuple[str, str]:
        """
        Generates subject and plain-text body for a given offer and ladder stage.
        Stage 1: Day 1 (No links)
        Stage 2: Day 3 (Deliver goods + link)
        Stage 3: Day 7 (Case stat & proof)
        Stage 4: Day 12 (Rotated offer)
        Stage 5: Day 17 (Rotated proof)
        Stage 6: Day 24 (Breakup email)
        """
        name = business.get("name", "your business")
        city = business.get("city") or business.get("country", "your area")
        niche = business.get("keyword", "business")
        rating = business.get("rating")
        reviews = business.get("reviews_count", 0)

        rating_clause = f" — {rating}★ rating in {city}" if rating else f" in {city}"

        # -------------------------------------------------------------
        # OFFER A: WEBSITE BUILD / REDESIGN
        # -------------------------------------------------------------
        if offer_type == "website":
            if stage == 1:
                subject = f"quick question about {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Found {name} online{rating_clause}, looks like you do solid work.\n\n"
                    f"I noticed people searching for a {niche} in {city} might have trouble checking out your services beforehand, "
                    f"so some end up going with competitors who have modern mobile pages.\n\n"
                    f"I put together a clean homepage mockup tailored for {name}. Want me to send over the preview link? Completely free either way.\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 2:
                subject = f"Re: quick question about {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is the mockup I put together for {name}: {mockup_link}\n\n"
                    f"It's designed to load fast on phones and make it easy for new customers to get in touch immediately.\n\n"
                    f"Take a look when you have a moment and let me know what you think.\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 3:
                subject = f"Re: quick question about {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Most businesses in {city} we work with see about 30-40% more inbound calls within the first month of switching to a modern layout.\n\n"
                    f"Would you be open to a 5-minute chat this week to see how it can bring in more jobs for {name}?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 4: # Rotate to AI Receptionist
                subject = f"missed calls at {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Switching gears — what happens when customers call {name} after hours or while your team is on a job?\n\n"
                    f"We install 24/7 AI assistants that answer immediately, answer common questions, and book jobs directly to your calendar.\n\n"
                    f"Want to hear a 60-second audio demo?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 5:
                subject = f"Re: missed calls at {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"One recovered missed call usually covers the entire system cost for 3 months.\n\n"
                    f"Worth exploring for {name}?\n\n"
                    f"{SENDER_NAME}"
                )
            else: # Breakup
                subject = f"closing the file on {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Closing the file on this for now. If upgrading your website or capturing missed calls ever becomes a priority, "
                    f"feel free to reach back out.\n\n"
                    f"Wishing {name} the best.\n\n"
                    f"{SENDER_NAME}"
                )
            return subject, body

        # -------------------------------------------------------------
        # OFFER B: AI RECEPTIONIST / CHATBOT
        # -------------------------------------------------------------
        elif offer_type == "receptionist":
            if stage == 1:
                subject = f"missed calls at {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Found {name} online{rating_clause} — clearly great work.\n\n"
                    f"Quick question: what happens when a customer calls after hours or when your team is busy on a job? "
                    f"For most {niche} companies, each missed call is a lost customer worth hundreds.\n\n"
                    f"We set up 24/7 AI receptionists that answer every call instantly, capture client details, and book jobs. "
                    f"Setup takes less than 24 hours.\n\n"
                    f"Want to hear a 60-second demo call? Happy to send it over.\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 2:
                subject = f"Re: missed calls at {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is the 60-second audio demo showing how the AI handles customer bookings: {mockup_link}\n\n"
                    f"It speaks naturally and logs the summary straight to your phone.\n\n"
                    f"Let me know what you think!\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 3:
                subject = f"Re: missed calls at {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Clients usually capture 4 to 8 extra jobs a month that would have otherwise gone to voicemail.\n\n"
                    f"Worth a 5-minute walkthrough to see how it fits {name}?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 4: # Rotate to Website
                subject = f"quick question about {name}'s website"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Also had a quick look at your current web setup — put together a modern mobile mockup that makes booking even faster.\n\n"
                    f"Should I send the link?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 5:
                subject = f"Re: quick question about {name}'s website"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is the layout preview: {mockup_link}\n\n"
                    f"Open to a quick chat this week?\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"closing the file on {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Closing the file on this for now. If you ever want to automate your phone bookings or upgrade your site, "
                    f"I kept everything ready for you.\n\n"
                    f"{SENDER_NAME}"
                )
            return subject, body

        # -------------------------------------------------------------
        # OFFER C: AI AUTOMATION / WORKFLOWS
        # -------------------------------------------------------------
        elif offer_type == "ai_automation":
            if stage == 1:
                subject = f"workflow automation for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Found {name} online — love what you're building in the {niche} space.\n\n"
                    f"I noticed a few manual workflows in operations and lead qualification that could easily be automated with custom AI tools, "
                    f"saving your team 15-20 hours a week.\n\n"
                    f"I mapped out a quick automation workflow blueprint specifically for {name}. Want me to send over the overview? Completely free either way.\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 2:
                subject = f"Re: workflow automation for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is the workflow blueprint I outlined for {name}: {mockup_link}\n\n"
                    f"It details how AI-powered tools can handle lead intake, data enrichment, and routine client follow-ups automatically.\n\n"
                    f"Take a look when you have a moment and let me know what you think.\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 3:
                subject = f"Re: workflow automation for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Teams similar to {name} usually cut response times down to seconds and eliminate hours of repetitive manual data entry each week.\n\n"
                    f"Would you be open to a 5-minute chat this week to see how it could work for {name}?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 4: # Rotate offer
                subject = f"custom AI assistants for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Switching angles slightly — beyond back-office automations, we also deploy internal AI assistants trained on your business docs to answer client inquiries instantly.\n\n"
                    f"Interested in seeing a quick interactive demo?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 5:
                subject = f"Re: custom AI assistants for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is a quick look at how the assistant integrates with your existing tools: {mockup_link}\n\n"
                    f"Open to exploring this for {name}?\n\n"
                    f"{SENDER_NAME}"
                )
            else: # Breakup
                subject = f"closing the file on {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Closing the file on this for now. If automating your workflows or exploring AI tools ever becomes a priority, "
                    f"feel free to reach back out anytime.\n\n"
                    f"Wishing {name} the best.\n\n"
                    f"{SENDER_NAME}"
                )
            return subject, body

        # -------------------------------------------------------------
        # OFFER D: SHORT-FORM VIDEO CLIPPING / CREATORS
        # -------------------------------------------------------------
        else:
            if stage == 1:
                subject = f"content clips for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Love the content you're putting out with {name}.\n\n"
                    f"Your long-form videos have great insights, but they could be generating 10x more reach if cut into viral short clips for Reels, Shorts, and TikTok.\n\n"
                    f"I went ahead and edited 3 sample vertical clips with dynamic captions from your recent content. Want me to send them over?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 2:
                subject = f"Re: content clips for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here are the 3 sample clips I cut for {name}: {mockup_link}\n\n"
                    f"Ready to post right away. Let me know what you think of the pacing and style!\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 3:
                subject = f"Re: content clips for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Our creators typically see 50k–200k extra monthly views without spending any extra time recording.\n\n"
                    f"Would you be open to a quick chat about turning your back-catalog into a daily short-form machine?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 4:
                subject = f"monetization & automation for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Apart from video editing, we also set up automated lead capture funnels for creators to convert followers into paying clients.\n\n"
                    f"Interested in seeing how other creators in your niche are doing it?\n\n"
                    f"{SENDER_NAME}"
                )
            elif stage == 5:
                subject = f"Re: monetization & automation for {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Here is a quick breakdown of how the funnel works: {mockup_link}\n\n"
                    f"Worth a quick chat?\n\n"
                    f"{SENDER_NAME}"
                )
            else:
                subject = f"closing the file on {name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"Closing the file for now. If you ever want to scale your short-form distribution or funnel, feel free to ping me.\n\n"
                    f"{SENDER_NAME}"
                )
            return subject, body
