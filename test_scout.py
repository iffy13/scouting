from scout_signals import analyse_html, score_whatsapp, score_receptionist
from services import SERVICES, get_service

def test_whatsapp_fit():
    html = '<a href="https://wa.me/971500000000">Chat</a><script src="shopify.com"></script><form></form>'
    sig = analyse_html({"": html})
    assert sig["has_wa_link"] and not sig["chat_widget"]
    score, ev = score_whatsapp(sig, {"reviews_count": 40}, {"emails": ["a@b.com"]})
    assert score >= 70, score

def test_skip_existing_bsp():
    sig = analyse_html({"": '<script src="https://cdn.wati.io/x.js"></script> wa.me/1'})
    score, ev = score_whatsapp(sig, {}, {})
    assert score == 0 and "WATI" in ev[0]

def test_unreachable():
    assert score_whatsapp(analyse_html({}), {}, {})[0] == 0

def test_registry():
    assert get_service("whatsapp_api").keywords
    assert set(SERVICES) == {"whatsapp_api", "receptionist", "render_3d", "book_trailer"}

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)


def test_optout_and_telegram_safe():
    import re
    import outreach, tg
    assert outreach.OPT_OUT.search("Please stop emailing me")
    assert outreach.OPT_OUT.search("Not interested, thanks")
    assert not outreach.OPT_OUT.search("Yes, tell me more about the cost")
    assert outreach.AUTO_REPLY.search("Automatic reply: I am out of office")
    if not tg.configured():
        assert tg.send("x") is False
