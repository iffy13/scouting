"""
Local-language emails and search terms, so a business in Mexico gets Spanish, in Brazil Portuguese, in Saudi Arabia
Arabic. Everything else keeps the English wording in messages.py / pitch.py / render3d.py / leadgen.py.

Which country gets which language: LANG_BY_COUNTRY below, or the LOCAL_LANGUAGES setting, for example
  LOCAL_LANGUAGES="MX=es,CO=es,AR=es,CL=es,BR=pt,SA=ar,KW=ar"     (AE=en sends English to the UAE)

Same rules as the English copy (HANDOFF section 6): plain text, no links, no exclamation marks, no "free" or
"guarantee" in any language, no claim of past clients or results, one easy question, an honest subject, and the
opt-out line in the reader's language. The opt-out words ("baja", "sair", "إلغاء") are in outreach.OPT_OUT.

Receptionist emails stay English only: the AI receptionist is offered in English-speaking countries.

Self-test and examples:   python localize.py
"""
import os
import random
import re
from typing import Dict, List, Optional, Tuple

LANG_BY_COUNTRY: Dict[str, str] = {"MX": "es", "CO": "es", "AR": "es", "CL": "es", "BR": "pt", "SA": "ar"}
LOCAL_SERVICES = ("whatsapp_api", "render_3d", "lead_gen")


def _overrides() -> Dict[str, str]:
    out = {}
    for part in (os.getenv("LOCAL_LANGUAGES") or "").split(","):
        if "=" in part:
            c, l = part.split("=", 1)
            out[c.strip().upper()] = l.strip().lower()
    return out


def language_for(country: Optional[str], service_id: Optional[str] = None) -> str:
    """'es', 'pt', 'ar' or 'en' for this country (and service: receptionist is always English)."""
    if service_id and service_id not in LOCAL_SERVICES:
        return "en"
    c = (country or "").upper()
    lang = _overrides().get(c) or LANG_BY_COUNTRY.get(c, "en")
    return lang if lang in POOLS else "en"


# ---------------------------------------------------------------- search terms
# English keyword (as in services.py) -> local search term. The English keyword stays on the lead, because niche
# detection and the OpenStreetMap tags use it; only the text sent to the search engine changes.
SEARCH_TERMS: Dict[str, Dict[str, str]] = {
    "es": {
        "ecommerce store": "tienda en línea", "dental clinic": "clínica dental", "med spa": "spa médico",
        "real estate agency": "inmobiliaria", "travel agency": "agencia de viajes", "language school": "escuela de idiomas",
        "private school": "colegio privado", "car dealership": "concesionaria de autos", "beauty salon": "salón de belleza",
        "fitness studio": "gimnasio", "furniture store": "mueblería", "restaurant delivery": "restaurante a domicilio",
        "interior design studio": "estudio de diseño de interiores", "interior designer": "diseñador de interiores",
        "commercial interior design firm": "diseño de interiores comerciales", "residential architect": "arquitecto residencial",
        "architecture firm": "despacho de arquitectura", "custom home builder": "constructora de casas",
        "luxury home builder": "constructora de casas de lujo", "design build firm": "diseño y construcción",
        "interior fit out company": "acabados de interiores", "home renovation company": "remodelación de casas",
        "kitchen remodeling company": "remodelación de cocinas", "bathroom remodeling company": "remodelación de baños",
        "property developer": "desarrolladora inmobiliaria", "real estate developer": "desarrollador inmobiliario",
        "villa developer": "desarrollo de casas residenciales", "landscape design company": "paisajismo",
        "pool builder": "construcción de albercas", "outdoor living designer": "diseño de terrazas y jardines",
        "marketing agency": "agencia de marketing", "digital marketing agency": "agencia de marketing digital",
        "seo agency": "agencia seo", "web design agency": "agencia de diseño web", "branding agency": "agencia de branding",
        "social media marketing agency": "agencia de redes sociales", "business coach": "coach de negocios",
        "executive coach": "coach ejecutivo", "sales training company": "capacitación en ventas",
        "management consultant": "consultoría empresarial", "managed it services": "servicios de ti administrados",
        "it support company": "soporte técnico empresarial", "accounting firm": "despacho contable",
        "bookkeeping services": "servicios de contabilidad", "commercial cleaning company": "limpieza comercial",
        "staffing agency": "agencia de personal", "recruitment agency": "agencia de reclutamiento",
        "commercial insurance broker": "corredor de seguros empresariales", "roofing company": "impermeabilización de techos",
        "solar installer": "instalación de paneles solares", "hvac company": "aire acondicionado",
        "commercial roofing contractor": "techos industriales", "window replacement company": "ventanas de aluminio",
        "dental implant clinic": "implantes dentales", "cosmetic surgery clinic": "clínica de cirugía estética",
        "physiotherapy clinic": "clínica de fisioterapia", "chiropractor": "quiropráctico",
        "aesthetics clinic": "clínica de estética",
    },
    "pt": {
        "ecommerce store": "loja virtual", "dental clinic": "clínica odontológica", "med spa": "clínica de estética",
        "real estate agency": "imobiliária", "travel agency": "agência de viagens", "language school": "escola de idiomas",
        "private school": "escola particular", "car dealership": "concessionária", "beauty salon": "salão de beleza",
        "fitness studio": "academia", "furniture store": "loja de móveis", "restaurant delivery": "restaurante delivery",
        "interior design studio": "escritório de design de interiores", "interior designer": "designer de interiores",
        "commercial interior design firm": "arquitetura comercial", "residential architect": "arquiteto residencial",
        "architecture firm": "escritório de arquitetura", "custom home builder": "construtora de casas",
        "luxury home builder": "construtora de alto padrão", "design build firm": "projeto e construção",
        "interior fit out company": "acabamentos de interiores", "home renovation company": "reformas residenciais",
        "kitchen remodeling company": "reforma de cozinha", "bathroom remodeling company": "reforma de banheiro",
        "property developer": "incorporadora", "real estate developer": "incorporadora imobiliária",
        "villa developer": "condomínio de casas", "landscape design company": "paisagismo",
        "pool builder": "construção de piscinas", "outdoor living designer": "projeto de área gourmet",
        "marketing agency": "agência de marketing", "digital marketing agency": "agência de marketing digital",
        "seo agency": "agência de seo", "web design agency": "agência de criação de sites", "branding agency": "agência de branding",
        "social media marketing agency": "agência de redes sociais", "business coach": "coach empresarial",
        "executive coach": "coach executivo", "sales training company": "treinamento de vendas",
        "management consultant": "consultoria empresarial", "managed it services": "serviços gerenciados de ti",
        "it support company": "suporte de ti para empresas", "accounting firm": "escritório de contabilidade",
        "bookkeeping services": "serviços contábeis", "commercial cleaning company": "limpeza comercial",
        "staffing agency": "agência de terceirização", "recruitment agency": "agência de recrutamento",
        "commercial insurance broker": "corretora de seguros empresariais", "roofing company": "telhados",
        "solar installer": "energia solar", "hvac company": "ar condicionado", "commercial roofing contractor": "coberturas industriais",
        "window replacement company": "esquadrias de alumínio", "dental implant clinic": "implante dentário",
        "cosmetic surgery clinic": "clínica de cirurgia plástica", "physiotherapy clinic": "clínica de fisioterapia",
        "chiropractor": "quiropraxia", "aesthetics clinic": "clínica de estética",
    },
}
CONNECTOR = {"es": "en", "pt": "em", "en": "in", "ar": "in"}
COUNTRY_LOCAL_NAMES = {"MX": "México", "CO": "Colombia", "AR": "Argentina", "CL": "Chile", "BR": "Brasil"}


def search_keyword(keyword: str, country: Optional[str]) -> str:
    """The keyword in the search language of that country (Arabic searches stay English: most Saudi business
    sites are bilingual and the map tags do not depend on language)."""
    lang = language_for(country)
    return SEARCH_TERMS.get(lang, {}).get((keyword or "").lower(), keyword)


def search_query(keyword: str, country: Optional[str], english_country_name: str) -> str:
    lang = language_for(country)
    place = COUNTRY_LOCAL_NAMES.get((country or "").upper(), english_country_name)
    return f"{search_keyword(keyword, country)} {CONNECTOR.get(lang, 'in')} {place}"


# ---------------------------------------------------------------- email pools
# Each pool: subjects, openers, seen_openers (WhatsApp link seen on the site), offers, closers, followups.
# "{name}" lines are dropped when the business name is not usable.
POOLS: Dict[str, Dict[str, Dict[str, List[str]]]] = {
    "es": {
        "whatsapp_api": {
            "subjects": ["consulta sobre su WhatsApp", "mensajes de WhatsApp fuera de horario",
                         "un solo WhatsApp para todo el equipo", "WhatsApp para {name}"],
            "openers": [
                "La mayoría de sus clientes prefiere escribir por WhatsApp antes que llamar, y espera respuesta en "
                "minutos. Cuando la respuesta tarda, la venta se enfría.",
                "Cuando los mensajes de WhatsApp llegan a un solo teléfono, una persona tiene que contestarlos todos "
                "y muchos se quedan sin respuesta fuera de horario.",
                "En {name} seguramente llegan muchas consultas por WhatsApp, y cada respuesta lenta es un cliente que "
                "se va con otro.",
            ],
            "seen_openers": [
                "Vi que su sitio web tiene un enlace directo a WhatsApp. Cuando un cliente escribe por ahí, ¿le llega "
                "a una sola persona o lo atiende un equipo?",
            ],
            "offers": [
                "Configuro la API oficial de WhatsApp Business: un mismo número que todo su equipo puede atender, con "
                "respuestas automáticas para preguntas frecuentes como precios, horarios y citas.",
                "Instalo la API oficial de WhatsApp Business con verificación de Meta, para que varias personas "
                "respondan desde una bandeja compartida y las consultas repetidas se contesten solas, de día o de noche.",
            ],
            "closers": ["¿Cómo están manejando hoy esos mensajes?",
                        "¿Le interesaría ver cómo funcionaría en su caso?",
                        "¿Le envío un breve resumen de cómo funciona y cuánto cuesta?"],
            "followups": [
                "Le escribo de nuevo por si mi mensaje anterior se perdió. ¿Quién responde los WhatsApp de {name} "
                "fuera de horario?",
                "Le escribo de nuevo por si mi mensaje anterior se perdió. ¿Quién responde sus mensajes de WhatsApp "
                "fuera de horario?",
                "Un último mensaje de mi parte. Si el WhatsApp ya lo tienen resuelto, no hay problema y no volveré a "
                "escribirle.",
            ],
        },
        "render_3d": {
            "subjects": ["imágenes antes de construir", "renders 3D para sus proyectos",
                         "sus clientes, viendo el proyecto terminado"],
            "openers": [
                "A muchos clientes les cuesta imaginar un espacio a partir de un plano o un moodboard, y esa duda "
                "retrasa la aprobación.",
                "Un render realista suele convencer más rápido que cualquier plano, sobre todo cuando el cliente "
                "todavía duda.",
                "Mostrar el proyecto terminado antes de empezar ayuda a cerrar la venta y evita cambios a mitad de obra.",
            ],
            "seen_openers": [],
            "offers": [
                "Creo renders 3D realistas de interiores y exteriores a partir de sus planos o bocetos, para que sus "
                "clientes vean exactamente lo que van a recibir.",
                "Hago visualizaciones 3D fotorrealistas de interiores, fachadas y espacios exteriores, listas para "
                "presentaciones, redes sociales y preventa.",
            ],
            "closers": ["¿Quiere que le envíe un par de ejemplos recientes?",
                        "¿Cómo presentan hoy los proyectos a sus clientes?",
                        "¿Le serviría ver algunas muestras y un precio de referencia?"],
            "followups": [
                "Le escribo de nuevo por si mi mensaje se perdió. ¿Le envío un par de ejemplos de renders para que "
                "juzgue la calidad?",
                "Un último mensaje de mi parte. Si ya tienen las visualizaciones cubiertas, no hay problema y no "
                "volveré a escribirle.",
            ],
        },
        "lead_gen": {
            "subjects": ["de dónde salen sus próximos clientes", "posibles clientes para {name}",
                         "10 contactos de muestra para su zona"],
            "openers": [
                "En muchos negocios los clientes nuevos llegan por rachas: un mes por recomendaciones y el siguiente "
                "casi nada.",
                "Encontrar a quién escribirle suele llevar más tiempo que el propio trabajo con el cliente.",
                "Buscar clientes nuevos a mano le quita horas a la semana que podría dedicar a sus clientes actuales.",
            ],
            "seen_openers": [],
            "offers": [
                "Preparo listas de empresas que encajan con su cliente ideal, con sitio web, correo verificado y, "
                "cuando aparece, el nombre del responsable.",
                "Armo listas de posibles clientes de su zona y su sector, con correos comprobados para que sus "
                "mensajes no reboten.",
            ],
            "closers": ["¿Le serviría una muestra de 10 contactos de su zona para juzgar la calidad?",
                        "¿Quiere que le prepare una muestra corta para su sector?",
                        "¿Cómo consiguen hoy los clientes nuevos?"],
            "followups": [
                "Le escribo de nuevo por si mi mensaje se perdió. ¿Le preparo una muestra de 10 contactos para que "
                "vea la calidad?",
                "Un último mensaje de mi parte. Si ya tienen la búsqueda de clientes resuelta, no hay problema y no "
                "volveré a escribirle.",
            ],
        },
    },
    "pt": {
        "whatsapp_api": {
            "subjects": ["uma pergunta sobre o seu WhatsApp", "mensagens de WhatsApp fora do horário",
                         "um só WhatsApp para toda a equipe", "WhatsApp da {name}"],
            "openers": [
                "A maioria dos clientes prefere mandar mensagem no WhatsApp a ligar, e espera resposta em minutos. "
                "Quando a resposta demora, a venda esfria.",
                "Quando as mensagens de WhatsApp chegam em um único celular, uma pessoa precisa responder tudo e "
                "muita coisa fica sem resposta fora do horário.",
                "Na {name} devem chegar muitas perguntas pelo WhatsApp, e cada resposta lenta é um cliente que "
                "fecha com outra empresa.",
            ],
            "seen_openers": [
                "Vi que o seu site tem um link direto para o WhatsApp. Quando um cliente manda mensagem por ali, ela "
                "chega para uma pessoa só ou para uma equipe?",
            ],
            "offers": [
                "Eu configuro a API oficial do WhatsApp Business: um único número que toda a sua equipe pode atender, "
                "com respostas automáticas para perguntas comuns como preços, horários e agendamentos.",
                "Eu implemento a API oficial do WhatsApp Business com verificação da Meta, para várias pessoas "
                "responderem em uma caixa compartilhada e as dúvidas repetidas serem respondidas sozinhas, de dia ou "
                "de noite.",
            ],
            "closers": ["Como vocês estão lidando com essas mensagens hoje?",
                        "Faz sentido ver como isso funcionaria no seu caso?",
                        "Posso enviar um resumo curto de como funciona e quanto custa?"],
            "followups": [
                "Estou escrevendo de novo caso a minha mensagem tenha se perdido. Quem responde o WhatsApp da {name} "
                "fora do horário?",
                "Estou escrevendo de novo caso a minha mensagem tenha se perdido. Quem responde o WhatsApp de vocês "
                "fora do horário?",
                "Uma última mensagem da minha parte. Se o WhatsApp já está resolvido, sem problema, e não volto a "
                "escrever.",
            ],
        },
        "render_3d": {
            "subjects": ["o projeto pronto antes da obra", "renders 3D para os seus projetos",
                         "imagens que ajudam a fechar projetos"],
            "openers": [
                "Muitos clientes têm dificuldade de imaginar um ambiente a partir de uma planta ou de um moodboard, e "
                "essa dúvida atrasa a aprovação.",
                "Uma imagem realista costuma convencer mais rápido do que qualquer planta, principalmente quando o "
                "cliente ainda está em dúvida.",
                "Mostrar o projeto pronto antes de começar ajuda a fechar a venda e evita mudanças no meio da obra.",
            ],
            "seen_openers": [],
            "offers": [
                "Eu crio renders 3D realistas de interiores e fachadas a partir das suas plantas ou esboços, para o "
                "cliente ver exatamente o que vai receber.",
                "Faço visualizações 3D fotorrealistas de interiores, fachadas e áreas externas, prontas para "
                "apresentações, redes sociais e pré-venda.",
            ],
            "closers": ["Quer que eu envie alguns exemplos recentes?",
                        "Como vocês apresentam os projetos aos clientes hoje?",
                        "Seria útil ver algumas amostras e um preço de referência?"],
            "followups": [
                "Estou escrevendo de novo caso a minha mensagem tenha se perdido. Posso enviar alguns exemplos de "
                "renders para você avaliar a qualidade?",
                "Uma última mensagem da minha parte. Se as imagens dos projetos já estão resolvidas, sem problema, e "
                "não volto a escrever.",
            ],
        },
        "lead_gen": {
            "subjects": ["de onde vêm os seus próximos clientes", "possíveis clientes para a {name}",
                         "10 contatos de amostra da sua região"],
            "openers": [
                "Em muitas empresas os clientes novos chegam em ondas: um mês por indicação e no outro quase nada.",
                "Descobrir para quem escrever costuma levar mais tempo do que o próprio trabalho com o cliente.",
                "Procurar clientes novos manualmente toma horas da semana que poderiam ir para quem já é cliente.",
            ],
            "seen_openers": [],
            "offers": [
                "Eu monto listas de empresas que combinam com o seu cliente ideal, com site, e-mail verificado e, "
                "quando aparece, o nome do responsável.",
                "Preparo listas de possíveis clientes da sua região e do seu setor, com e-mails conferidos para as "
                "suas mensagens não voltarem.",
            ],
            "closers": ["Uma amostra de 10 contatos da sua região ajudaria a avaliar a qualidade?",
                        "Quer que eu prepare uma amostra curta para o seu setor?",
                        "Como vocês conseguem clientes novos hoje?"],
            "followups": [
                "Estou escrevendo de novo caso a minha mensagem tenha se perdido. Posso preparar uma amostra de 10 "
                "contatos para você ver a qualidade?",
                "Uma última mensagem da minha parte. Se a busca por clientes já está resolvida, sem problema, e não "
                "volto a escrever.",
            ],
        },
    },
    "ar": {
        "whatsapp_api": {
            "subjects": ["سؤال سريع عن واتساب", "رسائل واتساب بعد ساعات العمل", "رقم واتساب واحد لكل الفريق"],
            "openers": [
                "أغلب العملاء يفضّلون مراسلتكم عبر واتساب بدل الاتصال، ويتوقعون رداً خلال دقائق. وعندما يتأخر الرد "
                "يفقد العميل اهتمامه.",
                "عندما تصل رسائل واتساب إلى جوال واحد فقط، يتحمّل شخص واحد الرد على كل شيء، وتبقى رسائل كثيرة بلا "
                "رد بعد ساعات العمل.",
            ],
            "seen_openers": [
                "لاحظت أن موقعكم يحتوي على رابط مباشر لواتساب. عندما يراسلكم عميل من خلاله، هل تصل الرسالة إلى شخص "
                "واحد أم إلى فريق؟",
            ],
            "offers": [
                "أقوم بإعداد واجهة واتساب للأعمال الرسمية (WhatsApp Business API): رقم واحد يرد منه فريقكم بالكامل، "
                "مع ردود تلقائية على الأسئلة المتكررة مثل الأسعار والمواعيد وأوقات العمل.",
                "أفعّل لكم واجهة واتساب للأعمال الرسمية مع توثيق حساب Meta، بحيث يرد أكثر من موظف من صندوق رسائل "
                "مشترك، وتُجاب الاستفسارات المتكررة تلقائياً ليلاً ونهاراً.",
            ],
            "closers": ["كيف تتعاملون مع هذه الرسائل حالياً؟",
                        "هل يهمكم أن تروا كيف سيعمل ذلك لديكم؟",
                        "هل أرسل لكم ملخصاً قصيراً عن طريقة العمل والتكلفة؟"],
            "followups": [
                "أكتب لكم مرة أخرى في حال لم تصلكم رسالتي السابقة. من يرد على رسائل واتساب لديكم بعد ساعات العمل؟",
                "هذه آخر رسالة مني. إذا كان واتساب لديكم منظماً بالفعل فلا بأس، ولن أراسلكم مجدداً.",
            ],
        },
        "render_3d": {
            "subjects": ["صور المشروع قبل التنفيذ", "تصاميم ثلاثية الأبعاد لمشاريعكم", "دعوا العميل يرى المشروع جاهزاً"],
            "openers": [
                "كثير من العملاء يصعب عليهم تخيّل المساحة من مخطط أو لوحة إلهام، وهذا التردد يؤخر الموافقة على التصميم.",
                "الصورة الواقعية تقنع العميل أسرع من أي مخطط، خاصة عندما يكون متردداً.",
                "عرض المشروع بشكله النهائي قبل البدء يساعد على إتمام البيع ويقلّل التعديلات أثناء التنفيذ.",
            ],
            "seen_openers": [],
            "offers": [
                "أصمّم صوراً ثلاثية الأبعاد واقعية للتصاميم الداخلية والواجهات انطلاقاً من مخططاتكم أو رسوماتكم، "
                "ليرى العميل ما سيحصل عليه بالضبط.",
                "أقدّم تصاميم ثلاثية الأبعاد بجودة قريبة من الواقع للمساحات الداخلية والواجهات والمساحات الخارجية، "
                "جاهزة للعروض ووسائل التواصل والبيع على الخارطة.",
            ],
            "closers": ["هل ترغبون أن أرسل لكم بعض الأمثلة الحديثة؟",
                        "كيف تعرضون مشاريعكم على العملاء حالياً؟",
                        "هل يفيدكم الاطلاع على بعض النماذج مع سعر تقريبي؟"],
            "followups": [
                "أكتب لكم مرة أخرى في حال لم تصلكم رسالتي السابقة. هل أرسل لكم بعض النماذج لتقييم الجودة؟",
                "هذه آخر رسالة مني. إذا كانت التصاميم ثلاثية الأبعاد متوفرة لديكم فلا بأس، ولن أراسلكم مجدداً.",
            ],
        },
        "lead_gen": {
            "subjects": ["من أين يأتي عملاؤكم القادمون", "قائمة عملاء محتملين لنشاطكم", "عينة من 10 جهات اتصال في منطقتكم"],
            "openers": [
                "في كثير من الشركات يأتي العملاء الجدد على دفعات: شهر مليء بالتوصيات وشهر شبه فارغ.",
                "البحث عمّن تراسلونه يأخذ غالباً وقتاً أطول من العمل نفسه مع العميل.",
                "البحث اليدوي عن عملاء جدد يستهلك ساعات من الأسبوع كان يمكن تخصيصها لخدمة العملاء الحاليين.",
            ],
            "seen_openers": [],
            "offers": [
                "أُعدّ قوائم بشركات تناسب عميلكم المثالي، تتضمن الموقع الإلكتروني وبريداً إلكترونياً تم التحقق منه، "
                "واسم المسؤول عند توفره.",
                "أجهّز قوائم عملاء محتملين في منطقتكم وقطاعكم، مع عناوين بريد تم فحصها حتى لا ترتد رسائلكم.",
            ],
            "closers": ["هل تفيدكم عينة من 10 جهات اتصال في منطقتكم لتقييم الجودة؟",
                        "هل أجهّز لكم عينة قصيرة لقطاعكم؟",
                        "كيف تحصلون على العملاء الجدد حالياً؟"],
            "followups": [
                "أكتب لكم مرة أخرى في حال لم تصلكم رسالتي السابقة. هل أجهّز لكم عينة من 10 جهات اتصال لتروا الجودة؟",
                "هذه آخر رسالة مني. إذا كان البحث عن العملاء منظماً لديكم فلا بأس، ولن أراسلكم مجدداً.",
            ],
        },
    },
}

GREETING = {
    "es": ("Hola,", "Hola, equipo de {name},"),
    "pt": ("Olá,", "Olá, equipe {name},"),
    "ar": ("السلام عليكم،", "السلام عليكم فريق {name}،"),
}
OPT_OUT_LINE = {
    "es": 'Si no le interesa, responda "baja" y no le escribiré más.',
    "pt": 'Se não for do seu interesse, responda "sair" e não volto a escrever.',
    "ar": 'إذا لم يكن الأمر مناسباً لكم، ردّوا بكلمة "إلغاء" ولن أراسلكم مرة أخرى.',
}
TITLES = {"founder": {"es": "Fundador", "pt": "Fundador", "ar": "المؤسس"}}
BANNED = re.compile(r"(gratis|grátis|garant|مجان|ضمان|https?://|www\.|[!¡])", re.I)


def _rnd(seed: str, slot: str) -> random.Random:
    return random.Random(f"{seed}:{slot}")


def _pick(seed: str, slot: str, pool: List[str], name_ok: bool) -> str:
    usable = [p for p in pool if name_ok or "{name}" not in p] or pool
    return _rnd(seed, slot).choice(usable)


OWNER_GREETING = {"es": "Hola, {owner},", "pt": "Olá, {owner},", "ar": "السلام عليكم {owner}،"}


def _hello(lang: str, name: Optional[str], owner: Optional[str] = None) -> str:
    if owner and len(owner) <= 25:
        return OWNER_GREETING[lang].format(owner=owner.split()[0])
    plain, with_name = GREETING[lang]
    return with_name.format(name=name) if name and len(name) <= 30 else plain


def footer(lang: str, sender: str, title: str, business: str, postal: str) -> str:
    t = TITLES.get((title or "").strip().lower(), {}).get(lang, title)
    comma = "، " if lang == "ar" else ", "
    lines = [sender, f"{t}{comma}{business}" if t else business, postal]
    return "\n".join(l for l in lines if l) + "\n\n" + OPT_OUT_LINE[lang]


def build_first(lang: str, service_id: str, name: Optional[str], evidence: str, seed: str,
                owner: Optional[str] = None) -> Tuple[str, str]:
    """(subject, body WITHOUT footer). `name` is None when the stored name is not a usable business name."""
    p = POOLS[lang][service_id]
    ok = bool(name)
    subject = _pick(seed, "subject", p["subjects"], ok).format(name=name or "")
    seen = service_id == "whatsapp_api" and "whatsapp" in (evidence or "").lower() and p["seen_openers"]
    opener = _pick(seed, "opener", p["seen_openers"] if seen else p["openers"], ok)
    offer = _pick(seed, "offer", p["offers"], ok)
    closer = _pick(seed, "closer", p["closers"], ok)
    body = f"{_hello(lang, name, owner)}\n\n{opener}\n\n{offer}\n\n{closer}".format(name=name or "")
    return subject, body


def build_followup(lang: str, service_id: str, name: Optional[str], seed: str, first_subject: str,
                   owner: Optional[str] = None) -> Tuple[str, str]:
    p = POOLS[lang][service_id]
    text = _pick(seed, "followup", p["followups"], bool(name)).format(name=name or "")
    # "Re: " in every language: it is what mail apps use to keep the follow up in the same conversation.
    return "Re: " + first_subject, f"{_hello(lang, name, owner)}\n\n{text}"


# ---------------------------------------------------------------- self-test
def _self_test() -> int:
    problems = 0
    count = 0

    def bad(msg):
        nonlocal problems
        problems += 1
        print("PROBLEM:", msg)

    for lang, services in POOLS.items():
        for sid, p in services.items():
            for key in ("subjects", "openers", "offers", "closers", "followups"):
                if not p.get(key):
                    bad(f"{lang}/{sid}: empty {key}")
            for i in range(300):
                seed = f"lead{i}.example"
                for name in ("Clínica Sol", None):
                    ev = "WhatsApp click-to-chat on the site" if i % 3 == 0 else ""
                    s, b = build_first(lang, sid, name, ev, seed)
                    fs, fb = build_followup(lang, sid, name, seed, s)
                    count += 1
                    for label, text in (("subject", s), ("body", b), ("followup", fb)):
                        if "{" in text or "}" in text:
                            bad(f"{lang}/{sid} {label} has an unrendered slot: {text[:80]}")
                        if BANNED.search(text):
                            bad(f"{lang}/{sid} {label} has a banned word or link: {BANNED.search(text).group(0)}")
                        if name is None and "Clínica" in text:
                            bad("name used when unusable")
                    words = len(b.split())
                    if not 25 <= words <= 90:
                        bad(f"{lang}/{sid} body has {words} words")
                    q = b.count("?") + b.count("؟")
                    if not 1 <= q <= 2:
                        bad(f"{lang}/{sid} body has {q} questions")
    # opt-out words in each footer must be caught by the reply classifier
    try:
        import outreach
        for lang, word in (("es", "baja"), ("pt", "sair"), ("ar", "إلغاء")):
            for reply in (word, word.capitalize(), f"{word}, gracias" if lang == "es" else word):
                if outreach.classify_reply(reply) != "optout":
                    bad(f"reply '{reply}' is not treated as an opt-out")
        for reply in ("No me interesa", "Não temos interesse", "غير مهتمين", "por favor no me escriba más"):
            if outreach.classify_reply(reply) != "optout":
                bad(f"reply '{reply}' is not treated as an opt-out")
        for reply in ("Sí, envíeme ejemplos", "Sim, pode mandar", "نعم أرسل لي التفاصيل", "¿Cuánto cuesta?"):
            if outreach.classify_reply(reply) != "positive":
                bad(f"reply '{reply}' is not treated as interested")
    except ImportError as e:
        print("note: outreach not importable here:", e)
    if language_for("MX", "receptionist") != "en" or language_for("BR", "whatsapp_api") != "pt":
        bad("language routing")
    if search_keyword("dental clinic", "MX") != "clínica dental" or search_keyword("dental clinic", "SA") != "dental clinic":
        bad("search keyword routing")
    print(f"rendered {count} emails, {problems} problems")
    return problems


if __name__ == "__main__":
    import sys
    if "--examples" in sys.argv:
        for lang in POOLS:
            for sid in LOCAL_SERVICES:
                s, b = build_first(lang, sid, "Clínica Sol" if lang != "ar" else None, "", f"x{sid}")
                print("=" * 60, lang, sid, "\nSubject:", s, "\n" + b + "\n\n" +
                      footer(lang, "<your name>", "Founder", "Iffy Studio", "<postal address>"))
    raise SystemExit(1 if _self_test() else 0)
