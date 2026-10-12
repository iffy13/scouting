import random
from typing import Tuple, Optional

GENRE_HOOKS = {
    "thriller": {
        "style": "high-tension psychological pacing, dark cinematic lighting, and heartbeat sound design",
        "audience": "thriller and mystery readers who crave pulse-pounding page-turners"
    },
    "fantasy": {
        "style": "epic worldbuilding scenes, atmospheric spell animations, and orchestral audio",
        "audience": "fantasy lovers searching for their next immersive series to binge"
    },
    "romance": {
        "style": "emotional character tension, romantic aesthetic typography, and trending TikTok audio",
        "audience": "romance fans and BookTok communities looking for intense emotional chemistry"
    },
    "scifi": {
        "style": "futuristic visual depth, atmospheric neon glow, and deep cosmic soundscapes",
        "audience": "sci-fi and cyberpunk fans hungry for mind-bending concepts"
    },
    "horror": {
        "style": "spine-chilling atmosphere, eerie ambient sound design, and gritty cinematic cuts",
        "audience": "horror enthusiasts looking for genuine goosebumps"
    },
    "nonfiction": {
        "style": "sharp dynamic typography, authority visuals, and punchy chapter highlights",
        "audience": "professionals and readers looking for actionable transformation"
    },
    "ya_fiction": {
        "style": "vibrant character-driven motion, dynamic color palettes, and energetic pacing",
        "audience": "young adult readers looking for compelling characters and high stakes"
    },
    "default": {
        "style": "cinematic 4K visuals, atmospheric audio design, and high-converting typography",
        "audience": "readers browsing for exciting new releases"
    }
}

class AuthorCopywriter:
    """
    100% Human, Emotional Copywriting Engine for 7 High-Ticket Author Services:
    1. book_trailer  - Cinematic 30s Book Trailers & 3D Video Teasers
    2. cover_design  - Book Cover Redesign & 3D Photorealistic Box Sets
    3. amazon_aplus  - Amazon KDP A+ Graphical Content & Banners
    4. audiobook     - Studio-grade Audiobook Narration & ACX Mastering
    5. content_batch - Monthly 20x BookTok / Reels Viral Video Batching
    6. author_website- Author Portfolio & Automated ARC Newsletter Launch Funnel
    7. kickstarter_kit - Deluxe Hardcover Crowdfunding Campaign Visual Kits
    """

    @staticmethod
    def generate_email(author_name: str, book_title: str, genre: str = "fiction", offer_service: str = "book_trailer", stage: int = 1) -> Tuple[str, str]:
        first_name = author_name.split()[0] if author_name and author_name != "Author" else "there"
        clean_title = book_title.strip().strip('"').strip("'") if book_title else "your book"
        genre_key = genre.lower() if genre in GENRE_HOOKS else "default"
        genre_info = GENRE_HOOKS.get(genre_key, GENRE_HOOKS["default"])

        # Service Router
        if offer_service == "cover_design":
            return AuthorCopywriter._pitch_cover_design(first_name, clean_title, stage)
        elif offer_service == "amazon_aplus":
            return AuthorCopywriter._pitch_amazon_aplus(first_name, clean_title, stage)
        elif offer_service == "audiobook":
            return AuthorCopywriter._pitch_audiobook(first_name, clean_title, genre_info, stage)
        elif offer_service == "content_batch":
            return AuthorCopywriter._pitch_content_batch(first_name, clean_title, genre_info, stage)
        elif offer_service == "author_website":
            return AuthorCopywriter._pitch_author_website(first_name, clean_title, stage)
        elif offer_service == "kickstarter_kit":
            return AuthorCopywriter._pitch_kickstarter(first_name, clean_title, stage)
        else:
            return AuthorCopywriter._pitch_book_trailer(first_name, clean_title, genre_info, stage)

    # 1. BOOK TRAILERS
    @staticmethod
    def _pitch_book_trailer(first_name: str, book_title: str, genre_info: dict, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = random.choice([f"Quick question about {book_title}", f"30s trailer concept for {book_title}", f"BookTok promo idea for {book_title}"])
            body = f"""Hi {first_name},

I came across {book_title} and really loved the premise.

Most authors find that static images struggle to get traction on TikTok and Instagram right now, whereas cinematic 30-second video trailers with {genre_info['style']} are driving huge pre-orders and reader interest.

We build Hollywood-style cinematic trailers and vertical teasers tailored for {genre_info['audience']}.

Would you be open to seeing a quick 15-second visual concept I put together for {book_title}?

No cost or commitment at all, just wanted to share the idea.

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Quick question about {book_title}"
            body = f"""Hi {first_name},

Following up briefly on my note from earlier this week.

We just completed a 30-second teaser for another author in your genre that helped them drive over 40k views on BookTok in their first weekend.

The visual concept I sketched for {book_title} uses {genre_info['style']} to make your opening hook impossible to scroll past.

Would you like me to send over a quick storyboard preview?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on {book_title}"
            body = f"""Hi {first_name},

I assume you are fully focused on your current writing schedule, so I will not follow up further.

If you ever want a cinematic 30-second book trailer or video teaser for {book_title} or an upcoming launch down the road, feel free to reach out anytime.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 2. BOOK COVER REDESIGN & 3D BOX SETS
    @staticmethod
    def _pitch_cover_design(first_name: str, book_title: str, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = random.choice([f"Cover concept & 3D mockups for {book_title}", f"Quick visual idea for {book_title}", f"3D render sample for {book_title}"])
            body = f"""Hi {first_name},

I was browsing recent releases and {book_title} caught my eye.

A lot of great books get overlooked on Amazon simply because their thumbnail cover does not match the current top-selling aesthetic in their category. 

We redesign book covers to match current Amazon bestseller benchmarks, complete with photorealistic 3D box set renders, paperback spines, and transparent promo mockups.

I would love to generate a complimentary 3D hardcover mockup and visual concept for {book_title} for you to check out.

Are you open to having a look?

Best regards,
Author Design Studio
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"3D sample for {book_title}"
            body = f"""Hi {first_name},

Checking in to see if you had a chance to look at my previous note regarding {book_title}.

Happy to pass over a free 3D promotional render of your book that you can use across your social media and newsletter.

Let me know if you would like me to send it over.

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 3. AMAZON KDP A+ CONTENT
    @staticmethod
    def _pitch_amazon_aplus(first_name: str, book_title: str, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = f"Amazon A+ graphical layout for {book_title}"
            body = f"""Hi {first_name},

I noticed your Amazon listing for {book_title} and thought the premise was fantastic.

One quick observation: listings that use full Amazon A+ graphical banners (character quote cards, moodboards, and world maps) typically convert 20% to 30% more browsing readers into paid buyers compared to plain text descriptions.

We design custom high-converting A+ Content graphic suites tailored specifically for indie authors.

Would you be open to seeing a sample A+ banner concept sketched for {book_title}?

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Amazon A+ graphical layout for {book_title}"
            body = f"""Hi {first_name},

Following up briefly on my note regarding {book_title}.

We recently updated the Amazon A+ graphics for another author in your genre, and their page conversion rate jumped by 28% within the first two weeks—turning cold traffic into actual buyers.

I already drafted a sample visual layout showing what a custom character art banner and review spotlight could look like for {book_title}.

Would you like me to send over the mockups?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 3:
            subject = f"Quick case study: Amazon sales conversion for {book_title}"
            body = f"""Hi {first_name},

Wanted to share a quick case study that might interest you.

Most indie authors spend heavily on Amazon ads or social promo, but lose half of potential readers right on the product page because plain text doesn't hold attention on mobile. Adding cohesive A+ modules with editorial review highlights and visual tropes gives readers an instant reason to buy.

Happy to share a case breakdown and a complimentary draft banner tailored to {book_title}.

Let me know if you would like to take a look.

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on Amazon A+ graphics for {book_title}"
            body = f"""Hi {first_name},

I assume updating your Amazon page design isn't a priority right now, so I will not follow up further.

If you ever want high-converting A+ Content graphics or visual banners for {book_title} or future releases down the line, feel free to reach out anytime.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 4. AUDIOBOOK PRODUCTION
    @staticmethod
    def _pitch_audiobook(first_name: str, book_title: str, genre_info: dict, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = f"Audiobook & Audible edition for {book_title}?"
            body = f"""Hi {first_name},

Reaching out because I really enjoyed the premise of {book_title}.

With audiobook consumption growing faster than any other publishing format on Audible and Spotify, having an audio edition opens up an entirely new revenue stream from readers who prefer listening.

We produce studio-grade audiobook narration with full ACX-compliant mastering at a fraction of traditional studio costs.

Are you planning an audiobook release for {book_title}? I would be glad to send over a free 2-minute sample narration from your opening chapter.

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Audiobook & Audible edition for {book_title}?"
            body = f"""Hi {first_name},

Touching base briefly on my previous email about {book_title}.

An indie author we worked with last month expanded into Audible and Spotify and saw audio sales make up over 35% of their total royalties in their first 60 days.

We can produce a complimentary 2-minute narration sample from {book_title} with voice talent matched to {genre_info['audience']}.

Would you like me to pass the sample over?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 3:
            subject = f"Untapped audio royalties for {book_title}"
            body = f"""Hi {first_name},

One quick thought regarding {book_title}:

Many authors hold off on audiobooks assuming the production takes months and costs thousands. With our streamlined ACX-mastered workflow, we handle casting, editing, and sound design end-to-end so your book can be live across Audible, Apple Books, and Spotify without any production hassle.

Would you be open to hearing a quick test sample from your opening pages?

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on audiobook production for {book_title}"
            body = f"""Hi {first_name},

I imagine you have plenty on your plate with writing and publishing right now, so I will step back and not follow up further.

If you ever decide to bring {book_title} or any future titles to Audible and audio platforms, don't hesitate to get in touch.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 5. MONTHLY BOOKTOK CONTENT BATCHING
    @staticmethod
    def _pitch_content_batch(first_name: str, book_title: str, genre_info: dict, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = f"Monthly BookTok & Reels video pack for {book_title}"
            body = f"""Hi {first_name},

Most authors I speak with love writing but hate having to edit vertical videos every single day for TikTok and Instagram.

We take your book excerpts, quotes, and tropes and turn them into a monthly package of 15 to 20 ready-to-post short video hooks formatted with trending audio and dynamic typography.

This lets you keep a consistent viral social presence without taking any time away from writing your next manuscript.

Would you like to see 2 sample video hooks we put together for {book_title}?

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Monthly BookTok & Reels video pack for {book_title}"
            body = f"""Hi {first_name},

Following up quickly on my note about video content for {book_title}.

One of our author clients recently generated over 85,000 views across Reels and TikTok using our monthly video hooks, which pushed their book back into Amazon's top 100 in their category.

The two sample hooks we drafted for {book_title} are crafted specifically for {genre_info['audience']}.

Would you like me to send over the 2 video previews for you to check out?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 3:
            subject = f"Zero-effort social content strategy for {book_title}"
            body = f"""Hi {first_name},

Reaching out with a quick alternative perspective:

The biggest hurdle for authors on BookTok isn't finding great quotes—it's the endless daily grind of video editing and trend research. With our monthly batching, you get 20 finished vertical videos delivered in one go, so your promo runs on autopilot while you focus entirely on your writing.

I'd love to share a couple of sample hooks formatted around the tropes in {book_title}.

Let me know if you'd be interested in seeing them.

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on BookTok content for {book_title}"
            body = f"""Hi {first_name},

I assume social video isn't on your radar at the moment, so I will close out my notes here.

If you ever want done-for-you monthly BookTok and Reels video batches for {book_title} or an upcoming launch, our door is always open.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 6. AUTHOR WEBSITE & NEWSLETTER LAUNCH FUNNEL
    @staticmethod
    def _pitch_author_website(first_name: str, book_title: str, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = f"Reader launch funnel & portfolio for {book_title}"
            body = f"""Hi {first_name},

I was looking up your author profile and wanted to connect.

Relying solely on Amazon algorithms can be risky. The most profitable indie authors build direct reader email lists using dedicated ARC (Advance Reader Copy) funnels and sleek author portfolios so their next launch hits the bestseller list on Day 1.

We design modern author portfolios with built-in newsletter signups, book catalog showcases, and direct-to-reader sales funnels.

Would it be helpful if I shared a quick layout preview designed for your book catalog?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Reader launch funnel & portfolio for {book_title}"
            body = f"""Hi {first_name},

Checking in briefly to follow up on my note regarding {book_title}.

We recently launched a reader funnel site for an indie author that captured over 1,200 newsletter subscribers ahead of their latest book launch, ensuring immediate Day 1 sales without relying on paid ads.

I'd be glad to share a complimentary wireframe layout designed around {book_title} and your backlist.

Would you like to take a look?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 3:
            subject = f"Direct reader relationships for {book_title}"
            body = f"""Hi {first_name},

A quick thought on building long-term author independence:

When retailers change their visibility algorithms, authors with an owned reader list continue selling consistently. A high-converting author site with automated sample chapter downloads turns one-time readers of {book_title} into lifelong fans who buy every future release directly.

I'd be happy to pass over a quick portfolio mockup tailored to your author brand.

Let me know if you would like me to share it.

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on author portfolio for {book_title}"
            body = f"""Hi {first_name},

I assume a website or reader funnel update isn't a priority right now, so I will wrap up here and not follow up further.

If you ever want a high-converting author website or ARC newsletter funnel for {book_title} in the future, feel free to get in touch.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body

    # 7. KICKSTARTER / CROWDFUNDING KIT
    @staticmethod
    def _pitch_kickstarter(first_name: str, book_title: str, stage: int) -> Tuple[str, str]:
        if stage == 1:
            subject = f"Visual assets & video teaser for {book_title}"
            body = f"""Hi {first_name},

I saw your upcoming publishing project for {book_title} and wanted to reach out.

Crowdfunding campaigns with high-impact video trailers and 3D reward tier graphics routinely raise 3x to 5x more funding because backers can immediately visualize the quality of the physical book.

We produce campaign video trailers, 3D deluxe foil mockup graphics, and stretch goal banners designed specifically for Kickstarter and Indiegogo publishing projects.

Would you be open to seeing a visual asset concept for your campaign?

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 2:
            subject = f"Re: Visual assets & video teaser for {book_title}"
            body = f"""Hi {first_name},

Following up briefly on my note regarding your campaign for {book_title}.

A campaign creator we collaborated with recently passed 400% of their funding goal within 48 hours—primarily driven by their 3D deluxe edition renders and high-energy pitch trailer.

I've sketched a preliminary visual concept showing how your reward tiers and special edition graphics for {book_title} could look.

Would you like me to send the preview over?

Best,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        elif stage == 3:
            subject = f"Maximizing backer pledges on {book_title}"
            body = f"""Hi {first_name},

One quick insight on publishing campaigns:

The difference between a funded project and an overfunded blockbuster usually comes down to backer perception in the first 10 seconds on your campaign page. Premium 3D foil mockups and stretch goal roadmap graphics instantly build trust and encourage higher tier pledges.

I'd love to share a visual asset pack concept built for {book_title}.

Let me know if you'd be open to taking a look.

Best regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
        else:
            subject = f"Closing out on campaign visuals for {book_title}"
            body = f"""Hi {first_name},

I assume you have all the campaign materials sorted for {book_title}, so I will step aside and won't follow up again.

If you ever need video trailers, 3D deluxe mockups, or reward tier graphics for a future crowdfunding launch, feel free to reach out anytime.

Warm regards,
Akdam Studios (akdamhq)
WhatsApp: +44 7853 164638"""
            return subject, body
