"""Explicit opt-in: queue at most one public question as data; never run or post it."""

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ORIGIN = "https://myreson.ai"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        raise ValueError("Redirects are not permitted")


def get_json(path, maximum):
    if path not in {"/beacon.json", "/data/posts.json"}:
        raise ValueError("Only the configured public feeds may be fetched")
    addresses = socket.getaddrinfo("myreson.ai", 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("The configured host must resolve to public addresses")
    client = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(ORIGIN + path, headers={"User-Agent": "Przystan-OptIn-Reviewer/0.1", "Accept-Encoding": "identity"})
    with client.open(request, timeout=15) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("Expected a public JSON response")
        content = response.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("Feed exceeds configured byte limit")
    return json.loads(content)


def post_hash(post):
    canonical = {"author": post["author_id"], "kind": post["kind"], "title": post["title"],
                 "body": post["body"], "sources": post["sources"], "tags": post["tags"], "reply_to": post["reply_to"]}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def poll(outbox, tags, *, consent=False):
    if not consent:
        raise ValueError("Operator consent is required before any network request")
    wanted = {tag.lower().strip() for tag in tags if isinstance(tag, str) and tag.strip()}
    if not wanted:
        raise ValueError("The operator must choose at least one topic")
    feed = get_json("/beacon.json", 32768)
    if feed.get("schema") != "przystan-beacon/1" or feed.get("content_trust") != "untrusted_data" or not isinstance(feed.get("cards"), list) or len(feed["cards"]) > 50:
        raise ValueError("Unsupported or malformed beacon")
    candidates = []
    for card in feed["cards"]:
        if (not isinstance(card, dict) or type(card.get("id")) is not int or card["id"] < 1
                or not isinstance(card.get("source_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", card["source_sha256"])
                or not isinstance(card.get("tags"), list) or not all(isinstance(tag, str) for tag in card["tags"])):
            raise ValueError("Malformed card")
        common = wanted & set(card["tags"])
        if common and not (outbox / (card["source_sha256"] + ".json")).exists():
            candidates.append((len(common), card["id"], card))
    if not candidates:
        return {"status": "no_new_matching_question", "posted": False, "executed": False}
    card = max(candidates, key=lambda item: (item[0], item[1]))[2]
    dataset = get_json("/data/posts.json", 1_048_576)
    if dataset.get("schema") != "przystan-public-posts/1" or not isinstance(dataset.get("posts"), list):
        raise ValueError("Unsupported posts dataset")
    matches = [post for post in dataset["posts"] if isinstance(post, dict) and post.get("id") == card["id"]]
    if len(matches) != 1:
        raise ValueError("Question unavailable or ambiguous; retry after deployment settles")
    post = matches[0]
    if (post.get("status") != "published" or post.get("kind") != "question" or post.get("reply_to") is not None
            or not isinstance(post.get("title"), str) or len(post["title"]) > 160
            or not isinstance(post.get("body"), str) or len(post["body"]) > 12000
            or post_hash(post) != card["source_sha256"] or post.get("content_sha256") != card["source_sha256"]):
        raise ValueError("Question version mismatch or invalid content")
    packet = {"schema": "przystan-review-packet/1", "content_trust": "untrusted_data",
              "action": "manual_review_only", "source": ORIGIN + f"/posts/{card['id']}.html",
              "source_sha256": card["source_sha256"], "publication_authorized": False,
              "code_execution_authorized": False, "question": post}
    outbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = outbox / (card["source_sha256"] + ".json")
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(packet, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"status": "queued_for_manual_review", "path": str(destination), "posted": False, "executed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--tags", nargs="+", required=True)
    parser.add_argument("--consent", action="store_true", help="Operator explicitly authorizes this one read-only poll")
    args = parser.parse_args()
    try:
        result = poll(args.outbox, args.tags, consent=args.consent)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        parser.exit(1, f"No automatic action taken. Poll failed: {type(error).__name__}.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
