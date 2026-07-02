#!/usr/bin/env python3
"""Story görselini Buffer üzerinden tüm bağlı platformlara postlar.

Workflow'dan env ile gelir: BUFFER_TOKEN, IMG_URL, BLOG_URL, META_FILE
"""
import json, subprocess, sys, os

TOKEN = os.environ["BUFFER_TOKEN"]
ORG_ID = "5ea568a297b7045b7834a7e8"
IMG_URL = os.environ["IMG_URL"]
BLOG_URL = os.environ.get("BLOG_URL", "https://basariustasi.com")
META_FILE = os.environ.get("META_FILE", "")


def gql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = subprocess.run(
        ["curl", "-s", "-X", "POST",
         "-H", f"Authorization: Bearer {TOKEN}",
         "-H", "Content-Type: application/json",
         "--data-binary", json.dumps(payload),
         "https://api.buffer.com/graphql"],
        capture_output=True, text=True
    )
    return json.loads(r.stdout)


# Metadata dosyasından caption'ları oku
if META_FILE and os.path.exists(META_FILE):
    with open(META_FILE) as f:
        meta = json.load(f)
    caption_ig = meta.get("caption", "💡 Haftanın ipucu\n\nDetaylar için ↑ linke tıkla\n\n#trendyol #trendyolsatici #eticaret")
    caption_fb = meta.get("caption_facebook", caption_ig)
    caption_li = meta.get("caption_linkedin", caption_ig)
    caption_tw = meta.get("caption_twitter", meta.get("title", "Haftanın İpucu") + "\n\n" + BLOG_URL)
else:
    caption_ig = "💡 Haftanın ipucu\n\nDetaylar için ↑ linke tıkla\n\n#trendyol #trendyolsatici #eticaret"
    caption_fb = caption_ig
    caption_li = caption_ig
    caption_tw = caption_ig

# Tüm kanalları çek
channels_data = gql(f'{{ channels(input: {{organizationId: "{ORG_ID}"}}) {{ id name service }} }}')
channels = channels_data.get("data", {}).get("channels", [])
print(f"Bulunan kanallar: {[(c['name'], c['service']) for c in channels]}")

CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status dueAt } }
    ... on InvalidInputError  { message }
    ... on LimitReachedError  { message }
    ... on UnauthorizedError  { message }
    ... on UnexpectedError    { message }
  }
}
"""


# Platform bazlı ayarlar
def get_post_input(channel):
    service = channel["service"]
    channel_id = channel["id"]

    if service == "instagram":
        return {
            "channelId": channel_id,
            "text": caption_ig,
            "assets": [{"image": {"url": IMG_URL}}],
            "schedulingType": "automatic",
            "mode": "addToQueue",
            "metadata": {"instagram": {"type": "story", "shouldShareToFeed": False}}
        }
    elif service == "facebook":
        return {
            "channelId": channel_id,
            "text": caption_fb + f"\n\n🔗 {BLOG_URL}",
            "assets": [{"image": {"url": IMG_URL}}],
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    elif service == "linkedin":
        return {
            "channelId": channel_id,
            "text": caption_li + f"\n\n{BLOG_URL}",
            "assets": [{"image": {"url": IMG_URL}}],
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    elif service in ("twitter", "x"):
        return {
            "channelId": channel_id,
            "text": caption_tw[:270] + f"\n{BLOG_URL}",
            "assets": [{"image": {"url": IMG_URL}}],
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    else:
        # Bilinmeyen platform — standart post
        return {
            "channelId": channel_id,
            "text": caption_ig,
            "assets": [{"image": {"url": IMG_URL}}],
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }


post_ids = []
errors = []

for ch in channels:
    service = ch["service"]
    name = ch["name"]
    print(f"\n→ {name} ({service}) için post oluşturuluyor...")
    inp = get_post_input(ch)
    result = gql(CREATE_POST, {"input": inp})
    post = result.get("data", {}).get("createPost", {}).get("post", {})
    if post.get("id"):
        print(f"  ✅ Başarı: {post['id']} — {post.get('dueAt','?')}")
        post_ids.append(f"{name}({service}):{post['id']}")
    else:
        err = result.get("data", {}).get("createPost", {}).get("message", str(result))
        print(f"  ❌ Hata: {err}")
        errors.append(f"{name}: {err}")

# Sonuçları dosyaya yaz (ntfy adımı için)
with open("/tmp/post_ids.txt", "w") as f:
    f.write("\n".join(post_ids))

if errors:
    with open("/tmp/post_errors.txt", "w") as f:
        f.write("\n".join(errors))
    print(f"\n⚠️ Hatalar: {errors}")
    sys.exit(1)

print(f"\n✅ Toplam {len(post_ids)} platform")
