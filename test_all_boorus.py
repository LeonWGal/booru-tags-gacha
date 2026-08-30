import asyncio
import sys
import os
import traceback

ext_dir = r"t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha"
sys.path.insert(0, ext_dir)

from scripts.boorus import get_client, SITE_DANBOORU, SITE_GELBOORU, SITE_RULE34, SITE_YANDERE

out_lines = []

async def test_direct(site_name, site_key, include_list, rating, min_score):
    out_lines.append(f"\n==========================================")
    out_lines.append(f"Testing direct {site_name} (site={site_key})...")
    client = get_client(site_key)
    try:
        post = await client.random_post(
            tags=include_list,
            exclude_tags=[],
            rating=rating,
            min_score=min_score,
        )
        if post:
            out_lines.append(f"SUCCESS! Got post ID: {post.id}")
            out_lines.append(f"Post URL: {post.post_url}")
            out_lines.append(f"Rating: {post.rating}, Score: {post.score}")
            out_lines.append(f"File URL: {post.file_url}")
            out_lines.append(f"Artists: {post.tags_artist}")
            out_lines.append(f"Characters: {post.tags_character}")
        else:
            out_lines.append(f"FAILURE: random_post returned None")
    except Exception as e:
        out_lines.append(f"EXCEPTION in random_post: {e}")
        out_lines.append(traceback.format_exc())

async def main():
    await test_direct("Danbooru", SITE_DANBOORU, ["1girl", "solo"], "safe", 20)
    await test_direct("Gelbooru", SITE_GELBOORU, ["scenery"], "safe", 0)
    await test_direct("Rule34", SITE_RULE34, ["solo"], "any", 0)
    await test_direct("Yande.re", SITE_YANDERE, ["solo"], "safe", 20)

    out_path = os.path.join(ext_dir, "test_all_output.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

if __name__ == "__main__":
    asyncio.run(main())
