
# app.py
from flask import Flask, request, make_response, jsonify, send_file, Response
import requests
import os

APP_PORT = int(os.environ.get("PORT", 5050))  # use 5050 by default

HTML_PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>Reddit → Pure Text</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:2rem;max-width:900px}
  label{display:block;margin:.5rem 0 .25rem}
  input,button{font-size:14px}
  pre{white-space:pre-wrap;border:1px solid #ddd;padding:1rem;background:#fafafa}
  .row{display:flex;gap:.5rem;align-items:center;margin:.75rem 0}
</style>

<h1>Reddit → Pure Text</h1>
<p>Paste any Reddit URL below. This page uses a <strong>local proxy</strong> to avoid browser CORS.</p>

<form id="f">
  <label>Reddit URL</label>
  <input id="url" placeholder="https://www.reddit.com/r/.../comments/.../" style="width:100%">
  <div class="row">
    <label><input type="checkbox" id="forceJson" checked> Append <code>.json</code> automatically</label>
  </div>
  <div class="row">
    <button type="submit">Convert to Text</button>
    <button type="button" id="clear">Clear</button>
    <button type="button" id="download">Download .txt</button>
  </div>
</form>

<h2>Output</h2>
<pre id="out"></pre>

<script>
const qs = s => document.querySelector(s);
const out = qs('#out');
const dlBtn = qs('#download');

qs('#clear').onclick = () => { out.textContent = ''; };

qs('#f').onsubmit = async (e)=>{
  e.preventDefault();
  out.textContent = 'Working…';
  const raw = qs('#url').value.trim();
  const forceJson = qs('#forceJson').checked;
  if(!raw){ out.textContent = 'Please paste a Reddit URL.'; return; }

  try{
    const u = new URL(raw);
    let path = u.pathname;
    if(forceJson && !path.endsWith('.json')) path += '.json';
    const jsonUrl = `https://www.reddit.com${path}${u.search||''}`;

    // Call local proxy to bypass CORS
    const proxy = `/fetch?url=${encodeURIComponent(jsonUrl)}`;

    const resp = await fetch(proxy);
    if(!resp.ok) throw new Error(`Proxy error: ${resp.status} ${resp.statusText}`);
    const data = await resp.json();
    const text = toText(data);
    out.textContent = text;

    dlBtn.onclick = ()=>{
      const blob = new Blob([text], {type:'text/plain'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'reddit_text.txt';
      a.click();
      URL.revokeObjectURL(a.href);
    };

  }catch(err){
    out.textContent = 'Error: '+err.message +
      '\\n\\nMake sure the app is served from http://127.0.0.1:%PORT%';
  }
};

// Convert Reddit JSON to readable Markdown-ish text
function toText(data){
  // Post + comments response is array [postListing, commentListing]
  if(Array.isArray(data) && data.length>=1){
    const post = data[0]?.data?.children?.[0]?.data || {};
    let md = `# ${post.title||''}\\n\\n` +
             `Author: u/${post.author||''}\\n` +
             `Subreddit: r/${post.subreddit||''}\\n` +
             `URL: https://www.reddit.com${post.permalink||''}\\n` +
             `Created (UTC): ${post.created_utc||''}\\n\\n`;
    if(post.selftext){ md += post.selftext + '\\n\\n'; }
    md += '---\\n## Comments\\n\\n';
    const comments = data[1]?.data?.children||[];
    md += comments.map(c=> renderComment(c,0)).join('\\n');
    return md.trim();
  }

  // Listing pages
  if(data?.data?.children){
    return data.data.children.map(ch=>{
      const d=ch.data||{};
      return `- ${d.title||d.body||''} — by ${d.author||''} (${d.subreddit_name_prefixed||d.subreddit||''})`;
    }).join('\\n');
  }

  return JSON.stringify(data,null,2);
}

function renderComment(node, depth){
  if(!node || node.kind==='more') return '';
  const d=node.data||{};
  const body = (d.body||'').replace(/\\r?\\n/g,' ');
  let s = `${'  '.repeat(depth)}- ${body} — u/${d.author||'[deleted]'} (score: ${d.score||0})\\n`;
  if(d.replies && d.replies.data && d.replies.data.children){
    for(const ch of d.replies.data.children){ s += renderComment(ch, depth+1); }
  }
  return s;
}
</script>
"""

app = Flask(__name__)

@app.route("/")
def home():
    # Serve the HTML with the correct port filled into the message
    page = HTML_PAGE.replace("%PORT%", str(APP_PORT))
    return Response(page, mimetype="text/html")

@app.route("/fetch")
def fetch():
    url = request.args.get("url", "")
    if not url:
        return make_response(("Missing 'url' parameter", 400))

    if not url.startswith("https://www.reddit.com/"):
        return make_response(("Only reddit.com URLs are allowed", 400))

    headers = {"User-Agent": "MyRedditTextTool/1.0 by your_username"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return make_response((f"Upstream fetch error: {e}", 502))

    resp = make_response(r.content)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # Allow the page (same origin: this Flask app) to fetch
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)

