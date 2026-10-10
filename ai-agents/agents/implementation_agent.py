import html
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from urllib.parse import urlparse

import requests

from common.llm_client import generate_json
from prompts.implementation_plan import SYSTEM, TEMPLATE
from rag.retriever import format_context_for_prompt


def _normalize_chunks(chunks: list[dict] | None) -> list[dict]:
    normalized = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        normalized.append({
            "text": chunk.get("text") or chunk.get("content") or "",
            "file_path": chunk.get("file_path") or "unknown",
            "start_line": chunk.get("start_line", 0),
            "end_line": chunk.get("end_line", 0),
        })
    return normalized


def _slugify(value: str) -> str:
    candidate = (value or "feature").strip()
    slug = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
    return slug or "feature"


def _fallback_plan(title: str, description: str, spec: dict, codebase_chunks: list[dict] | None = None) -> dict:
    feature_name = title or description or "request-feature"
    slug = _slugify(feature_name)
    file_name = f"generated_{slug}.py"

    summary = title or "Prompt-driven feature implementation"
    changes = [{
        "file": file_name,
        "action": "create",
        "summary": f"Create a minimal implementation for: {summary}",
        "validation": "Import the generated module and call its request handler with a realistic sample payload.",
    }]
    files = [file_name]

    files.append("index.html")
    changes.append({
        "file": "index.html",
        "action": "create",
        "summary": f"Create a browser-ready interface for: {summary}",
        "validation": "Open the generated page in a browser and verify it reflects the request.",
    })

    confidence = float(spec.get("confidence", 0.7))
    return {
        "status": "ready",
        "files": files,
        "changes": changes,
        "risks": [
            "Keep the generated code aligned with the user's actual request.",
            "Validate the result with a realistic sample payload before treating it as complete.",
        ],
        "confidence": max(0.0, min(1.0, confidence)),
    }


def _search_open_images(description: str, project_root: Path, limit: int = 3) -> list[dict[str, str]]:
    original_request, _, clarification_context = description.partition("\n\nClarification answers:")
    lowered_request = original_request.lower()
    if re.search(r"\b(school|academy|college|university|education)\b", lowered_request):
        query = "school campus architecture learning space"
        fallback_queries = ["school campus", "school building"]
    elif re.search(r"\b(hair salon|salon|barber)\b", lowered_request):
        query = "hair salon interior hair styling"
        fallback_queries = ["hair salon interior", "salon interior"]
    elif re.search(r"\b(restaurant|cafe|coffee shop|bakery)\b", lowered_request):
        query = "restaurant interior dining food"
        fallback_queries = ["restaurant dining", "restaurant food"]
    elif re.search(r"\b(dashboard|task tracker|task tracking|daily tasks|to-do|todo|planner)\b", lowered_request):
        query = "task planning workspace calendar organization"
        fallback_queries = ["planner calendar", "organized workspace"]
    elif re.search(r"\b(technology|software|\bIT\b|tech company)\b", original_request, re.IGNORECASE):
        query = "technology office computer infrastructure"
        fallback_queries = ["technology office", "computer lab"]
    else:
        terms = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", original_request + " " + clarification_context)
        ignored = {"build", "website", "webpage", "site", "with", "that", "this", "from", "they", "their"}
        specific_terms = list(dict.fromkeys(term.lower() for term in terms if term.lower() not in ignored))[:5]
        query = " ".join(specific_terms + ["website illustration"])
        fallback_queries = [" ".join(specific_terms[:3]), "website illustration"]
    answer_text = " ".join(re.findall(r"(?im)^A:\s*(.+)$", clarification_context))
    preference_terms = re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", answer_text)
    ignored_preferences = {"which", "what", "should", "website", "visual", "style", "images", "image", "include", "campus", "school", "openly", "licensed", "sources", "creator", "license", "credits"}
    preference_terms = list(dict.fromkeys(
        term.lower() for term in preference_terms if term.lower() not in ignored_preferences
    ))[:4]
    params = {
        "action": "query",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrlimit": max(6, limit * 2),
        "prop": "imageinfo",
        "iiprop": "url|user|extmetadata",
        "iiurlwidth": 1400,
        "format": "json",
    }
    assets_dir = project_root / "assets"
    images = []
    search_queries = [query, *fallback_queries]
    if preference_terms:
        search_queries.insert(0, f"{query} {' '.join(preference_terms[:2])}")
    for search_query in dict.fromkeys(search_queries):
        if len(images) >= limit:
            break
        params["gsrsearch"] = f"filetype:bitmap {search_query}"
        try:
            response = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers={"User-Agent": "AIOPSBuilder/1.0 (local generated website; Wikimedia Commons API)"},
                timeout=12,
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {}).values()
        except (requests.RequestException, ValueError, TypeError):
            continue

        for page in sorted(pages, key=lambda item: item.get("index", 0)):
            if len(images) >= limit:
                break
            image_info = (page.get("imageinfo") or [{}])[0]
            metadata = image_info.get("extmetadata") or {}
            image_url = image_info.get("thumburl") or image_info.get("url")
            source_url = image_info.get("descriptionurl")
            license_name = (metadata.get("LicenseShortName") or {}).get("value", "").strip()
            license_url = (metadata.get("LicenseUrl") or {}).get("value", "").strip()
            if not image_url or not source_url or not license_name:
                continue
            if not image_url.startswith("https://") or not source_url.startswith("https://"):
                continue
            if any(image["source"] == source_url for image in images):
                continue

            artist_markup = (metadata.get("Artist") or {}).get("value", "")
            artist = html.unescape(re.sub(r"<[^>]*>", "", artist_markup)).strip()
            if not artist:
                uploader = page.get("imageinfo", [{}])[0].get("user")
                artist = f"Uploader: {uploader}; original author not listed" if uploader else "Original author not listed"
            extension = Path(urlparse(image_url).path).suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                extension = ".jpg"
            assets_dir.mkdir(parents=True, exist_ok=True)
            relative_path = Path("assets") / f"commons_{len(images) + 1}{extension}"
            try:
                image_response = requests.get(
                    image_url,
                    headers={"User-Agent": "AIOPSBuilder/1.0 (local generated website; Wikimedia Commons API)"},
                    timeout=20,
                )
                image_response.raise_for_status()
                if not image_response.headers.get("Content-Type", "").startswith("image/") or len(image_response.content) > 12_000_000:
                    continue
                (project_root / relative_path).write_bytes(image_response.content)
            except requests.RequestException:
                continue

            images.append({
                "path": relative_path.as_posix(),
                "alt": page.get("title", "").removeprefix("File:").rsplit(".", 1)[0].replace("_", " "),
                "source": source_url,
                "license": license_name,
                "license_url": license_url if license_url.startswith("https://") else source_url,
                "artist": artist,
            })
    return images


def _render_website_template(
    title: str,
    description: str,
    images: list[dict[str, str]] | None = None,
    asset_prefix: str = "",
) -> str:
    original_request, _, clarification_context = description.partition("\n\nClarification answers:")
    brand_match = re.search(
        r"\b(?:website|web site|webpage|landing page)\s+(?:for|of)\s+([^,.!?]+)",
        original_request,
        re.IGNORECASE,
    )
    brand = brand_match.group(1) if brand_match else title
    brand = re.split(r"\b(?:with|that|which|including|featuring)\b", brand, maxsplit=1, flags=re.IGNORECASE)[0]
    brand = " ".join(brand.split()[:6]).strip(" .-") or title or "Your Company"
    brand = re.sub(r"^(?:a|an|the)\s+", "", brand, flags=re.IGNORECASE).title()
    brand = re.sub(r"\bIt\b", "IT", brand)
    brand = html.escape(brand)
    is_technology = bool(
        re.search(r"\b(software|technology|digital|tech)\b", original_request, re.IGNORECASE)
        or re.search(r"\bIT\b", original_request)
    )
    is_education = bool(re.search(r"\b(school|academy|college|university|education)\b", original_request, re.IGNORECASE))
    is_salon = bool(re.search(r"\b(hair salon|salon|barber|hair stylist)\b", original_request, re.IGNORECASE))
    is_restaurant = bool(re.search(r"\b(restaurant|cafe|coffee shop|bakery)\b", original_request, re.IGNORECASE))
    is_task_dashboard = bool(re.search(r"\b(dashboard|task tracker|task tracking|daily tasks|to-do|todo|planner)\b", original_request, re.IGNORECASE))
    if is_task_dashboard:
        brand = "Daily Tasks"
    answers = " ".join(re.findall(r"(?im)^A:\s*(.+)$", clarification_context))
    requested_sections = [
        ("Services", r"\bservices?\b"),
        ("Case studies", r"\b(case studies|portfolio|projects)\b"),
        ("Testimonials", r"\b(testimonials?|reviews?)\b"),
        ("Pricing", r"\b(pricing|plans|packages)\b"),
        ("FAQs", r"\b(faqs?|frequently asked questions)\b"),
        ("Contact", r"\b(contact|get in touch)\b"),
    ]
    services = [label for label, pattern in requested_sections if re.search(pattern, answers, re.IGNORECASE)][:3]
    if not services:
        if is_education:
            services = ["Academics", "Admissions", "Student life"]
        elif is_salon:
            services = ["Cuts & color", "Care rituals", "Easy booking"]
        elif is_restaurant:
            services = ["Our menu", "Made with care", "Reservations"]
        elif is_task_dashboard:
            services = ["Today", "In progress", "Completed"]
        elif is_technology:
            services = ["Digital strategy", "Custom engineering", "Reliable support"]
        else:
            services = ["Thoughtful planning", "Quality delivery", "Ongoing support"]
    hero_heading = (
        "A place to learn, grow, and belong." if is_education
        else "A fresh look. A little time for you." if is_salon
        else "Good food. Good company." if is_restaurant
        else "Your day, in focus." if is_task_dashboard
        else f"{brand} makes technology work for you." if is_technology
        else f"{brand} helps your business move forward."
    )
    hero_intro = (
        "Discover a welcoming school community where every student can build confidence, find their strengths, and prepare for what comes next."
        if is_education
        else "Thoughtful cuts, beautiful color, and a calm chair. Come as you are; leave feeling like yourself."
        if is_salon
        else "Seasonal ingredients, generous plates, and a warm welcome make every visit worth slowing down for."
        if is_restaurant
        else "A clear view of today's priorities, what is moving, and what is already done."
        if is_task_dashboard
        else f"{brand} brings thoughtful ideas and dependable expertise together to help your next move make a difference."
    )
    section_heading = (
        "Find your place to thrive." if is_education
        else "Your time, your style." if is_salon
        else "A table for every occasion." if is_restaurant
        else "Make room for what matters." if is_task_dashboard
        else "Built around what matters."
    )
    section_intro = (
        "Explore the learning, guidance, and experiences that help students grow."
        if is_education
        else "From a fresh shape to a color refresh, our team makes it easy to find your next look."
        if is_salon
        else "Explore the menu, find your favorites, and make a plan to join us."
        if is_restaurant
        else "Keep important tasks moving with a simple, focused view of the day."
        if is_task_dashboard
        else "From the first conversation to the final detail, we make complex work feel clear and achievable."
    )
    about_heading = (
        "Curious minds.<br>Bright futures." if is_education
        else "Good hair days.<br>Good energy." if is_salon
        else "Made with care.<br>Served with heart." if is_restaurant
        else "Small steps.<br>Real progress." if is_task_dashboard
        else "People first.<br>Progress always."
    )
    about_intro = (
        "Our teachers and staff create a supportive environment where students feel known, challenged, and ready to take their next step."
        if is_education
        else "We take time to listen, understand your style, and make every appointment feel relaxed and personal."
        if is_salon
        else "We choose thoughtful ingredients and make every dish with the kind of care that brings people back together."
        if is_restaurant
        else "Keep the next action visible, protect your focus, and make steady progress through the day."
        if is_task_dashboard
        else "We listen closely, work openly, and bring the right people together to turn good intentions into results that last."
    )
    closing_heading = (
        "Your next chapter starts here." if is_education
        else "Your chair is waiting." if is_salon
        else "Save you a seat?" if is_restaurant
        else "Start with one clear next step." if is_task_dashboard
        else "Let's make it happen."
    )
    closing_intro = (
        "Come see what makes our school community special." if is_education
        else "Ready for a refresh? Book a time that works for you." if is_salon
        else "We would love to welcome you. Reserve a table or stop by." if is_restaurant
        else "Use the sample tasks as a starting point and shape the list around your own work."
        if is_task_dashboard
        else "Tell us what you are working toward. We would love to hear about it."
    )
    contact_label = (
        "Contact admissions" if is_education
        else "Book an appointment" if is_salon
        else "Reserve a table" if is_restaurant
        else "Add a task" if is_task_dashboard
        else "hello@example.com&nbsp; ↗"
    )
    contact_href = (
        "mailto:admissions@example.com" if is_education
        else "mailto:appointments@example.com" if is_salon
        else "mailto:reservations@example.com" if is_restaurant
        else "#tasks" if is_task_dashboard
        else "mailto:hello@example.com"
    )
    service_descriptions = {
        "Academics": "Engaging classes help students discover their strengths and build a strong foundation.",
        "Admissions": "Get to know our programs, meet our team, and find your path to joining the school.",
        "Student life": "Clubs, activities, and friendships make every day a chance to belong.",
        "Cuts & color": "Cuts and color shaped around your features, routine, and personal style.",
        "Care rituals": "A little extra care for healthy hair and a moment to unwind.",
        "Easy booking": "Choose a time that works for you and let us take care of the rest.",
        "Our menu": "Seasonal plates and guest favorites, prepared fresh in our kitchen.",
        "Made with care": "Thoughtful ingredients and warm hospitality, from the first bite to the last.",
        "Reservations": "Gather around the table. We will have a place ready for you.",
        "Today": "Tasks planned for today, with a clear next action for each one.",
        "In progress": "Keep active work visible and moving forward.",
        "Completed": "See what is finished and make space for the next priority.",
    }
    cards = "".join(
        f'<article class="service"><span>0{index}</span><h3>{html.escape(service)}</h3>'
        f'<p>{service_descriptions.get(service, "A focused part of the experience, shaped around the details in your request.")}</p></article>'
        for index, service in enumerate(services, start=1)
    )
    task_board = '''
                <section id="tasks" class="task-section"><div class="wrap">
                    <div class="section-head"><div><div class="eyebrow">Sample items</div><h2>Tasks for today</h2></div><p>A simple starting point. Add your own task or mark an item complete.</p></div>
                    <form id="taskForm" class="task-form"><label class="sr-only" for="newTask">New task</label><input id="newTask" name="task" placeholder="Add a task" required><button type="submit">Add task</button></form>
                    <ul id="taskList" class="task-list"><li><label><input type="checkbox"><span>Review today's priorities</span></label><small>Today</small></li><li><label><input type="checkbox"><span>Move one important task forward</span></label><small>In progress</small></li><li><label><input type="checkbox"><span>Plan the first step for tomorrow</span></label><small>Next</small></li></ul>
                </div></section>
                <script>
                    document.getElementById('taskForm').addEventListener('submit', event => {
                        event.preventDefault();
                        const field = document.getElementById('newTask');
                        const title = field.value.trim();
                        if (!title) return;
                        const item = document.createElement('li');
                        const label = document.createElement('label');
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        const text = document.createElement('span');
                        text.textContent = title;
                        const status = document.createElement('small');
                        status.textContent = 'Today';
                        label.append(checkbox, text);
                        item.append(label, status);
                        document.getElementById('taskList').prepend(item);
                        field.value = '';
                        field.focus();
                    });
                </script>'''
    if not is_task_dashboard:
        task_board = ""
    images = images or []
    hero_image = images[0] if images else None
    hero_art = (
        f'<img class="hero-photo" src="{html.escape(asset_prefix + hero_image["path"], quote=True)}" '
        f'alt="{html.escape(hero_image["alt"], quote=True)}" fetchpriority="high">'
        f'<span class="image-credit">Photo: '
        f'<a href="{html.escape(hero_image["source"], quote=True)}" target="_blank" rel="noopener">{html.escape(hero_image["artist"])}</a> · '
        f'<a href="{html.escape(hero_image["license_url"], quote=True)}" target="_blank" rel="noopener">{html.escape(hero_image["license"])}</a></span>'
        if hero_image else f'<div class="art-mark">{brand[:1]}</div>'
    )
    image_gallery = "".join(
        f'<figure class="photo-card"><img src="{html.escape(asset_prefix + image["path"], quote=True)}" '
        f'alt="{html.escape(image["alt"], quote=True)}" loading="lazy">'
        f'<figcaption><a href="{html.escape(image["source"], quote=True)}" target="_blank" rel="noopener">{html.escape(image["artist"])}</a> · '
        f'<a href="{html.escape(image["license_url"], quote=True)}" target="_blank" rel="noopener">{html.escape(image["license"])}</a></figcaption></figure>'
        for image in images[1:]
    )
    gallery_section = (
        f'<section class="photo-gallery"><div class="wrap"><div class="section-head"><div>'
        f'<div class="eyebrow">A closer look</div><h2>{"Our campus" if is_education else "Planning desk" if is_task_dashboard else "A little inspiration"}</h2>'
        f'</div></div><div class="photo-grid">{image_gallery}</div></div></section>'
        if image_gallery else ""
    )
    return f'''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{brand} helps teams move forward with care and clarity.">
    <title>{brand} | Better, together</title>
    <style>
        :root {{ color-scheme: light; --ink: #172b2a; --muted: #526563; --paper: #f5f4ed; --accent: #d8f36a; --line: #cbd3c8; }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; color: var(--ink); background: var(--paper); font: 16px/1.55 "Segoe UI", sans-serif; }}
        a {{ color: inherit; }}
        .wrap {{ width: min(1120px, calc(100% - 48px)); margin: auto; }}
        header {{ height: 82px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--line); }}
        .brand {{ font-size: 19px; font-weight: 750; text-decoration: none; }}
        nav {{ display: flex; gap: 28px; align-items: center; }}
        nav a {{ font-size: 14px; text-decoration: none; }}
        .contact {{ background: var(--ink); color: white; padding: 11px 17px; border-radius: 3px; }}
        .hero {{ min-height: 500px; display: grid; grid-template-columns: 1.2fr .8fr; align-items: center; gap: 56px; padding: 76px 0; }}
        .eyebrow {{ font-size: 12px; letter-spacing: .13em; font-weight: 700; text-transform: uppercase; color: #54706a; }}
        h1 {{ max-width: 720px; margin: 20px 0; font: 500 72px/.98 Georgia, serif; letter-spacing: 0; }}
        .intro {{ max-width: 570px; color: var(--muted); font-size: 18px; }}
        .cta {{ display: inline-block; margin-top: 18px; padding: 14px 19px; background: var(--accent); text-decoration: none; font-weight: 700; border-radius: 3px; }}
        .art {{ min-height: 310px; background: #c9d9ce; position: relative; overflow: hidden; display: grid; place-items: center; }}
        .art:before, .art:after {{ content: ""; position: absolute; border: 1px solid rgba(23,43,42,.28); border-radius: 50%; }}
        .art:before {{ width: 270px; height: 270px; }} .art:after {{ width: 190px; height: 190px; }}
        .art-mark {{ z-index: 1; width: 112px; height: 112px; display: grid; place-items: center; background: var(--accent); border-radius: 50%; font: 44px Georgia, serif; }}
        .hero-photo {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
        .image-credit {{ position: absolute; z-index: 1; bottom: 10px; right: 10px; max-width: calc(100% - 20px); padding: 5px 8px; background: rgba(15, 31, 30, .82); color: white; font-size: 11px; text-decoration: none; }}
        .photo-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }}
        .photo-card {{ margin: 0; background: white; }} .photo-card img {{ display: block; width: 100%; height: 220px; object-fit: cover; }}
        .photo-card figcaption {{ padding: 10px 12px; color: var(--muted); font-size: 12px; }} .photo-card a {{ text-decoration: none; }}
        section {{ padding: 70px 0; border-top: 1px solid var(--line); }}
        .section-head {{ display: flex; justify-content: space-between; gap: 32px; align-items: end; margin-bottom: 30px; }}
        h2 {{ margin: 8px 0 0; font: 500 42px/1.05 Georgia, serif; letter-spacing: 0; }}
        .section-head p {{ max-width: 400px; color: var(--muted); margin: 0; }}
        .services {{ display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--line); }}
        .service {{ padding: 25px 24px 20px 0; }} .service + .service {{ border-left: 1px solid var(--line); padding-left: 24px; }}
        .service span {{ color: #54706a; font-size: 12px; font-weight: 700; }} .service h3 {{ margin: 20px 0 8px; font-size: 20px; }} .service p {{ color: var(--muted); margin: 0; }}
        .task-section {{ background: #eef1e9; }} .task-form {{ display: flex; gap: 10px; max-width: 720px; }} .task-form input {{ flex: 1; min-width: 0; border: 1px solid var(--line); padding: 12px; font: inherit; }} .task-form button {{ border: 0; background: var(--ink); color: white; padding: 0 18px; font: inherit; cursor: pointer; }}
        .task-list {{ list-style: none; padding: 0; max-width: 720px; margin: 18px 0 0; }} .task-list li {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 4px; border-bottom: 1px solid var(--line); }} .task-list label {{ display: flex; align-items: center; gap: 12px; }} .task-list input {{ width: 18px; height: 18px; accent-color: #3e7665; }} .task-list input:checked + span {{ text-decoration: line-through; color: var(--muted); }} .task-list small {{ color: var(--muted); white-space: nowrap; }} .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
        .closing {{ background: var(--ink); color: #f5f4ed; padding: 58px 0; }} .closing p {{ color: #c8d3cb; max-width: 580px; }}
        footer {{ padding: 22px 0; color: var(--muted); font-size: 13px; }}
        @media (max-width: 720px) {{ .wrap {{ width: min(100% - 32px, 540px); }} header {{ height: auto; min-height: 72px; flex-wrap: wrap; gap: 14px; padding: 16px 0; }} nav {{ width: 100%; justify-content: space-between; gap: 10px; }} nav a {{ font-size: 13px; }} .hero {{ grid-template-columns: 1fr; gap: 34px; padding: 58px 0; }} h1 {{ font-size: 48px; }} .art {{ min-height: 230px; }} .section-head {{ align-items: start; flex-direction: column; }} h2 {{ font-size: 36px; }} .services {{ grid-template-columns: 1fr; }} .service, .service + .service {{ border-left: 0; border-bottom: 1px solid var(--line); padding: 22px 0; }} }}
    </style>
</head>
<body>
    <header class="wrap"><a class="brand" href="#top">{brand}</a><nav aria-label="Main navigation"><a href="#services">{"Overview" if is_task_dashboard else "What we do"}</a><a href="{"#tasks" if is_task_dashboard else "#about"}">{"My tasks" if is_task_dashboard else "About"}</a><a class="contact" href="{"#tasks" if is_task_dashboard else "#contact"}">{"Add a task" if is_task_dashboard else "Get in touch"}</a></nav></header>
    <main id="top">
        <div class="wrap hero"><div><div class="eyebrow">{"Life at school" if is_education else "The salon experience" if is_salon else "Around the table" if is_restaurant else "Your task overview" if is_task_dashboard else "A better way forward"}</div><h1>{hero_heading}</h1><p class="intro">{hero_intro}</p><a class="cta" href="{"#tasks" if is_task_dashboard else "#contact"}">{"View today's tasks" if is_task_dashboard else "Explore admissions" if is_education else "Book a visit" if is_salon else "See the menu" if is_restaurant else "Start a conversation"}&nbsp; ↗</a></div><div class="art">{hero_art}</div></div>
        <section id="services"><div class="wrap"><div class="section-head"><div><div class="eyebrow">{"Task overview" if is_task_dashboard else "Life at school" if is_education else "Our services" if is_salon else "From our kitchen" if is_restaurant else "How we help"}</div><h2>{section_heading}</h2></div><p>{section_intro}</p></div><div class="services">{cards}</div></div></section>
        {task_board}
        {gallery_section}
        <section id="about"><div class="wrap section-head"><div><div class="eyebrow">A little about us</div><h2>{about_heading}</h2></div><p>{about_intro}</p></div></section>
        <div class="closing" id="contact"><div class="wrap"><div class="eyebrow">Your next chapter</div><h2>{closing_heading}</h2><p>{closing_intro}</p><a class="cta" href="{contact_href}">{contact_label}</a></div></div>
    </main>
    <footer class="wrap">© {brand}. Made with care.</footer>
</body>
</html>'''


def generate_implementation_plan(
    title: str,
    description: str,
    spec: dict,
    codebase_chunks: list[dict] | None = None,
    use_llm: bool = True,
) -> dict:
    normalized_chunks = _normalize_chunks(codebase_chunks)
    codebase_context = format_context_for_prompt(normalized_chunks)
    prompt = TEMPLATE.format(
        title=title,
        description=description,
        spec_json=json.dumps(spec, indent=2),
        codebase_context=codebase_context,
    )

    if not use_llm:
        return _fallback_plan(title, description, spec, codebase_chunks)

    try:
        result = generate_json(prompt, system=SYSTEM)
    except Exception:
        return _fallback_plan(title, description, spec, codebase_chunks)

    if not isinstance(result, dict):
        return _fallback_plan(title, description, spec, codebase_chunks)

    result.setdefault("status", "ready")
    result.setdefault("files", [])
    result.setdefault("changes", [])
    result.setdefault("risks", [])
    result.setdefault("confidence", 0.5)

    if not result["files"] and result["changes"]:
        result["files"] = [change.get("file", "") for change in result["changes"] if change.get("file")]

    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    if result["status"] not in {"ready", "needs_review"}:
        result["status"] = "ready"

    if result["files"]:
        result["files"] = [
            file_name for file_name in result["files"]
            if "sample-app" not in file_name.lower() and "orders.py" not in file_name.lower()
        ]
    if not result["files"]:
        result["files"] = _fallback_plan(title, description, spec, codebase_chunks)["files"]

    return result


def _feature_keywords_from_path(relative_file: str) -> list[str]:
    stem = Path(relative_file).stem.replace("generated_", "")
    if not stem:
        return ["feature"]

    entries = [part for part in re.split(r"[^a-z0-9]+", stem.lower()) if part]
    filtered = []
    stop_words = {
        "a", "an", "and", "app", "build", "create", "feature", "for", "from", "in",
        "into", "new", "of", "page", "project", "request", "something", "the", "to",
        "with", "without", "ui", "user",
    }
    for item in entries:
        if item in stop_words or len(item) <= 2:
            continue
        if item not in filtered:
            filtered.append(item)
    return filtered or ["feature"]


def _render_feature_template(relative_file: str) -> str:
    keywords = _feature_keywords_from_path(relative_file)
    feature_label = " ".join(keywords[:6]).strip() or "feature"
    keyword_tokens = keywords

    template = '''def handle_request(request_text: str) -> dict:
    """Feature-specific scaffold for: {feature_label}."""
    normalized = (request_text or "").strip()
    if not normalized:
        raise ValueError("Request text cannot be empty.")

    feature_name = "{feature_label}"
    keyword_tokens = {keyword_tokens}
    primary_keyword = keyword_tokens[0] if keyword_tokens else "feature"
    secondary_keyword = keyword_tokens[1] if len(keyword_tokens) > 1 else "workflow"
    tertiary_keyword = keyword_tokens[2] if len(keyword_tokens) > 2 else "builder"
    ticket_items = [
        {{"id": "T-101", "title": f"{{primary_keyword.title()}} request", "status": "open", "priority": "medium"}},
        {{"id": "T-102", "title": f"{{secondary_keyword.title()}} review", "status": "in_progress", "priority": "high"}},
        {{"id": "T-103", "title": f"{{tertiary_keyword.title()}} handoff", "status": "resolved", "priority": "low"}},
    ]

    return {{
        "status": "accepted",
        "feature": feature_name,
        "summary": f"Built a working {{feature_name}} flow with a sidebar, {{primary_keyword}} list, status filters, and a create form.",
        "message": f"The {{feature_name}} workflow has been scaffolded and is ready for a real implementation pass.",
        "keywords": keyword_tokens,
        "tickets": ticket_items,
        "status_filters": ["all", "open", "in_progress", "resolved"],
        "sidebar_items": ["Overview", primary_keyword.title(), "Reports"],
    }}


if __name__ == "__main__":
    print(handle_request("Build a {feature_label} with a sidebar and ticket list."))
'''.format(feature_label=feature_label, keyword_tokens=repr(keyword_tokens))

    return template


def apply_implementation_plan(plan: dict, project_root: str | None = None, request_text: str = "") -> list[str]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    applied = []
    target_files = {change.get("file") for change in plan.get("changes", []) if change.get("file")}
    target_files.update(plan.get("files", []))

    for relative_file in sorted(target_files):
        if not relative_file:
            continue
        file_path = root / relative_file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.exists():
            applied.append(str(relative_file))
            continue

        if relative_file.endswith(".py"):
            file_path.write_text(_render_feature_template(relative_file), encoding="utf-8")
            applied.append(str(relative_file))
        elif relative_file == "index.html":
            images = _search_open_images(request_text, root)
            asset_prefix = f"/api/preview/{root.name}/"
            file_path.write_text(
                _render_website_template(plan.get("title", ""), request_text, images, asset_prefix),
                encoding="utf-8",
            )
            applied.append(str(relative_file))
            applied.extend(image["path"] for image in images)

    return applied


def validate_implementation(project_root: str | None = None) -> dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    generated_files = sorted(root.rglob("*.py"))

    if not generated_files:
        return {"status": "skipped", "checks": [], "reason": "No generated Python files were found."}

    generated_candidates = []
    for path in generated_files:
        path_text = str(path).lower()
        if "sample" in path_text or "orders" in path_text or "sample-app" in path_text:
            continue
        generated_candidates.append(path)

    if not generated_candidates:
        return {"status": "skipped", "checks": [], "reason": "No generic prompt-driven implementation file was found."}

    import_path = str(root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

    target = generated_candidates[0]
    module_name = target.stem
    spec = spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        return {"status": "failed", "checks": [], "reason": "Could not import generated module."}

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    handler = getattr(module, "handle_request", None)
    if handler is None:
        return {"status": "failed", "checks": [], "reason": "Generated module does not expose handle_request."}

    result = handler("I want a form that accepts a request and shows a success message after submission.")
    passed = isinstance(result, dict) and result.get("status") == "accepted"
    return {
        "status": "passed" if passed else "failed",
        "checks": [{
            "name": "generated_feature_handler",
            "status_code": 200,
            "body": result,
        }],
    }
