"""
Dieu khien trinh duyet (Playwright) cho GUI.

Luu dang nhap bang storage_state.json (on dinh hon launch_persistent_context
tren macOS — tranh SingletonLock / CDP dut khi user dieu huong).

Chay 1 thread rieng. GUI <-> worker: cmd_q / evt_q.
"""
from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_DATA = HERE / ".browser"              # cache chrome (tuy chon)
STATE_FILE = HERE / ".browser_state.json"  # cookies / localStorage Skool
USER_DATA.mkdir(parents=True, exist_ok=True)


def san_file(s):
    s = re.sub(
        "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
        "\u2190-\u21FF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D]",
        "",
        s or "",
    )
    s = re.sub(r'[<>:"/\\|?*]', "", s).strip()
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "chuong"


def _is_closed_err(e) -> bool:
    s = str(e).lower()
    return any(
        x in s
        for x in (
            "has been closed",
            "target closed",
            "browser has been closed",
            "context or browser has been closed",
            "connection closed",
            "target page, context or browser",
            "browser closed",
            "protocol error",
            "session closed",
        )
    )


# JS: danh sach chuong — nhieu fallback
JS_LIST = r"""() => {
  function fromAllCourses(ac, grp) {
    if (!ac || !Array.isArray(ac) || !ac.length) return null;
    return {
      group: grp,
      loggedIn: true,
      chapters: ac.map((c, i) => ({
        i: i + 1,
        id: c.id || c.courseId || (c.course && c.course.id) || String(i),
        title: (c.metadata && c.metadata.title)
          || (c.course && c.course.metadata && c.course.metadata.title)
          || c.title || c.name || c.id || ('Chapter ' + (i + 1))
      }))
    };
  }
  function groupFromLoc() {
    try {
      const p = location.pathname.split('/').filter(Boolean);
      if (p[0] && !['settings','@me','discovery','signin','signup','www'].includes(p[0]))
        return p[0];
    } catch (e) {}
    return '';
  }
  const el = document.getElementById('__NEXT_DATA__');
  let d = null;
  try { if (el) d = JSON.parse(el.textContent); } catch (e) { d = null; }
  const grp = (d && d.query && d.query.group) || groupFromLoc();
  if (d) {
    const pp = (d.props && d.props.pageProps) || {};
    let hit = fromAllCourses(pp.allCourses, grp);
    if (hit) return hit;
    hit = fromAllCourses(pp.courses || pp.classroomCourses || pp.courseList, grp);
    if (hit) return hit;
    if (pp.group && pp.group.allCourses) {
      hit = fromAllCourses(pp.group.allCourses, grp || pp.group.slug);
      if (hit) return hit;
    }
    if (pp.course && pp.course.siblings) {
      hit = fromAllCourses(pp.course.siblings, grp);
      if (hit) return hit;
    }
  }
  try {
    const links = Array.from(document.querySelectorAll('a[href*="/classroom/"]'));
    const seen = new Map();
    for (const a of links) {
      const m = (a.getAttribute('href') || '').match(/\/classroom\/([a-zA-Z0-9_-]+)/);
      if (!m) continue;
      const id = m[1];
      if (!id || id === 'undefined' || seen.has(id)) continue;
      // bo link chi toi /classroom (khong id)
      let title = (a.textContent || '').trim().replace(/\s+/g, ' ');
      if (!title || title.length < 2) title = id;
      if (title.length > 120) title = title.slice(0, 117) + '...';
      seen.set(id, title);
    }
    if (seen.size) {
      return {
        group: grp || groupFromLoc(),
        loggedIn: true,
        chapters: Array.from(seen.entries()).map(([id, title], i) => ({ i: i + 1, id, title }))
      };
    }
  } catch (e) {}
  return null;
}"""

JS_DUMP = r"""async () => {
  const GROUP = location.pathname.split('/')[1];
  const d = JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
  const pp = d.props.pageProps, buildId = d.buildId, cid = d.query.course;
  if (!pp.course || !pp.course.children) return { ok:false, err:'not_chapter' };
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  function inline(ns){return (ns||[]).map(n=>{if(n.type==='text'){let t=n.text||'';const mk=(n.marks||[]).map(m=>m.type);if(mk.includes('code'))t='`'+t+'`';if(mk.includes('bold'))t='**'+t+'**';if(mk.includes('italic'))t='*'+t+'*';const lk=(n.marks||[]).find(m=>m.type==='link');if(lk&&lk.attrs&&lk.attrs.href)t='['+t+']('+lk.attrs.href+')';return t;}if(n.type==='hardBreak')return '  \n';return '';}).join('');}
  function blocks(a,dep){dep=dep||0;const o=[];for(const b of (a||[])){const t=b.type;if(t==='paragraph')o.push(inline(b.content));else if(t==='heading')o.push('#'.repeat((b.attrs&&b.attrs.level)||2)+' '+inline(b.content));else if(t==='blockquote')o.push('> '+blocks(b.content,dep).join('\n> '));else if(t==='codeBlock')o.push('```\n'+inline(b.content)+'\n```');else if(t==='bulletList')for(const li of (b.content||[]))o.push('  '.repeat(dep)+'- '+blocks(li.content,dep+1).join('\n').trim());else if(t==='orderedList'){let i=(b.attrs&&b.attrs.start)||1;for(const li of (b.content||[]))o.push('  '.repeat(dep)+(i++)+'. '+blocks(li.content,dep+1).join('\n').trim());}else if(t==='listItem')o.push(blocks(b.content,dep).join('\n'));else if(t==='image')o.push('![]('+((b.attrs&&(b.attrs.src||b.attrs.url))||'')+')');else if(b.content)o.push(blocks(b.content,dep).join('\n'));}return o;}
  function descToMd(x){if(!x)return '';let s=String(x);if(s.startsWith('[v2]')){try{return blocks(JSON.parse(s.slice(4)),0).join('\n\n').replace(/\n{3,}/g,'\n\n').trim();}catch(e){return '';}}return s.trim();}
  function embedFromText(s){
    if(!s) return '';
    const m = String(s).match(/https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?[^\s"'<>]+|youtu\.be\/[\w-]+|loom\.com\/share\/[\w-]+[^\s"'<>]*|vimeo\.com\/\d+|stream\.video\.skool\.com\/[^\s"'<>]+)/i);
    return m ? m[0] : '';
  }
  function pickVideo(rpp, lm){
    // 1) external link tren metadata
    let url = ((lm && lm.videoLink) || '').trim();
    if (url) return {url, kind:'ext'};
    // 2) native Mux / Skool stream
    const pv = rpp && rpp.video;
    if (pv) {
      if (pv.playbackId && pv.playbackToken)
        return {url:'https://stream.video.skool.com/'+pv.playbackId+'.m3u8?token='+pv.playbackToken, kind:'native'};
      if (pv.video_url) return {url:String(pv.video_url).trim(), kind:'ext'};
      if (pv.url) return {url:String(pv.url).trim(), kind:'ext'};
    }
    // 3) link nhung trong mo ta
    const emb = embedFromText(lm && lm.desc);
    if (emb) return {url:emb, kind:'embed'};
    return {url:'', kind:'none'};
  }
  async function resolveRes(raw){let arr=[];try{arr=typeof raw==='string'?JSON.parse(raw):(raw||[]);}catch(e){arr=[];}const out=[];for(const r of (arr||[])){if(r.link){out.push({type:'link',file_name:r.title||r.link,url:r.link});continue;}if(r.file_id){let u='';for(let a=0;a<3&&!u;a++){try{const rs=await fetch('https://api2.skool.com/files/'+r.file_id+'/download-url?expire=28800',{method:'POST',credentials:'include'});if(rs.ok)u=(await rs.text()).trim();}catch(e){}if(!u)await sleep(500*(a+1));}out.push({type:'file',file_name:r.file_name||r.title||'file',url:u});}}return out;}
  function leaves(ws,tr,acc){acc=acc||[];for(const w of (ws||[])){const o=w.course;if(!o)continue;const t=(o.metadata&&o.metadata.title)||'';const k=w.children||[];if(k.length)leaves(k,tr.concat([t]),acc);else acc.push({trail:tr.concat([t]),obj:o});}return acc;}
  function nest(items,setLeaf){const roots=[];for(const it of items){let lv=roots;for(let i=0;i<it.trail.length;i++){const ti=it.trail[i],last=i===it.trail.length-1;let nd=lv.find(n=>n.title===ti&&(!!n.__c!==last));if(!nd){nd={title:ti,children:[]};if(last)setLeaf(nd,it);else nd.__c=true;lv.push(nd);}lv=nd.children;}}return roots;}
  function clean(ns,vid){for(const n of ns){if(n.__c){delete n.__c;if(vid)n.url='';}clean(n.children||[],vid);}return ns;}
  const title=(pp.course.course&&pp.course.course.metadata&&pp.course.course.metadata.title)||cid;
  const lvs=leaves(pp.course.children,[],[]); let native=0,ext=0,none=0;
  const vi=[],mi=[];
  for(const lf of lvs){
    let url='', desc=(lf.obj.metadata&&lf.obj.metadata.desc)||'', resRaw=(lf.obj.metadata&&lf.obj.metadata.resources)||null, kind='none';
    // retry: API thinh thoang tra video=null o lan 1
    for(let a=0;a<5;a++){
      try{
        const r=await fetch('/_next/data/'+buildId+'/'+GROUP+'/classroom/'+cid+'.json?md='+lf.obj.id+'&group='+GROUP+'&course='+cid,{credentials:'include',headers:{'x-nextjs-data':'1'}});
        if(r.ok){
          const j=await r.json(), rpp=j.pageProps||{};
          let lm=null;
          JSON.stringify(rpp.course,(k,v)=>{if(v&&typeof v==='object'&&v.id===lf.obj.id&&v.metadata)lm=v.metadata;return v;});
          if(lm){ if(lm.desc) desc=lm.desc; if(lm.resources) resRaw=lm.resources; }
          const picked=pickVideo(rpp, lm||lf.obj.metadata||{});
          url=picked.url; kind=picked.kind;
          if(url || a>=3) break;  // co video hoac da thu du
        }
      }catch(e){}
      await sleep(400*(a+1));
    }
    if(kind==='native') native++; else if(url) ext++; else none++;
    const dm=descToMd(desc); const res=await resolveRes(resRaw);
    // links trong mo ta (Notion/Gemini/PDF/...) — extras se ghi links.md
    const linkSet=[];
    const re=/https?:\/\/[^\s"'<>\]]+/gi;
    let mm; const blob=(desc||'')+' '+JSON.stringify(res||[]);
    while((mm=re.exec(blob))){ const u=mm[0].replace(/[).,;}>]+$/,'').replace(/\\u0026/g,'&'); if(u&&!linkSet.includes(u)) linkSet.push(u); }
    let videoId=null;
    try{
      // lay videoId tu metadata goc neu co
      const r2=await fetch('/_next/data/'+buildId+'/'+GROUP+'/classroom/'+cid+'.json?md='+lf.obj.id+'&group='+GROUP+'&course='+cid,{credentials:'include',headers:{'x-nextjs-data':'1'}});
      if(r2.ok){ const j2=await r2.json(); let lm2=null; JSON.stringify((j2.pageProps||{}).course,(k,v)=>{if(v&&v.id===lf.obj.id&&v.metadata)lm2=v.metadata;return v;}); if(lm2&&lm2.videoId) videoId=lm2.videoId; }
    }catch(e){}
    vi.push({trail:lf.trail,url,video_id:videoId});
    mi.push({trail:lf.trail,desc_md:dm,resources:res,links:linkSet,video_id:videoId,url:url||''});
    await sleep(120);
  }
  const vidTree=[{title,url:'',children:clean(nest(vi,(n,it)=>{n.url=it.url; if(it.video_id)n.video_id=it.video_id;}),true)}];
  const metaTree=[{title,children:clean(nest(mi,(n,it)=>{n.desc_md=it.desc_md;n.resources=it.resources;n.links=it.links;n.video_id=it.video_id;if(it.url)n.url=it.url;}),false)}];
  return {ok:true,chapter:title,total:lvs.length,with_video:native+ext,native,ext,none,vid:JSON.stringify(vidTree),meta:JSON.stringify(metaTree)};
}"""


class SkoolBrowser:
    def __init__(self):
        self.cmd_q: queue.Queue = queue.Queue()
        self.evt_q: queue.Queue = queue.Queue()
        self.group = None
        self._p = None
        self._browser = None
        self._ctx = None
        self._page = None
        self._auto_list_done = False  # chi tu-list 1 lan moi lan vao classroom
        self._last_status_url = ""
        self._t = threading.Thread(target=self._run, daemon=True, name="skool-browser")
        self._t.start()

    def emit(self, **kw):
        self.evt_q.put(kw)

    def send(self, **kw):
        self.cmd_q.put(kw)

    def open(self):
        self.send(type="open")

    def open_course(self, url: str):
        """Mo trinh duyet va di toi URL Classroom cua khoa (hoac URL Skool bat ky)."""
        self.send(type="open_course", url=(url or "").strip())

    def list_chapters(self):
        self.send(type="list")

    def dump(self, chapters, out_dir, all_titles=None):
        self.send(
            type="dump",
            chapters=chapters,
            out_dir=str(out_dir),
            all_titles=all_titles,
        )

    def quit(self):
        self.send(type="quit")

    # ---------- worker ----------
    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self.emit(type="error", msg=f"Chua cai Playwright: {e}")
            return
        try:
            with sync_playwright() as p:
                self._p = p
                self.emit(type="ready")
                while True:
                    try:
                        cmd = self.cmd_q.get(timeout=1.2)
                    except queue.Empty:
                        # theo doi URL trinh duyet — GUI hien thi + tu lay chuong
                        try:
                            self._poll_status()
                        except Exception:
                            pass
                        continue
                    if cmd.get("type") == "quit":
                        break
                    try:
                        self._handle(cmd)
                    except Exception as e:
                        if _is_closed_err(e):
                            self.emit(
                                type="log",
                                msg="Ket noi trinh duyet bi dut — dang mo lai...",
                            )
                            self._teardown(kill_chrome=True)
                            try:
                                self._handle(cmd)
                            except Exception as e2:
                                self.emit(
                                    type="error",
                                    msg=(
                                        f"{e2}\n\n"
                                        "Hay dong het cua so «Chrome for Testing», "
                                        "bam «1. Mo Skool» roi thu lai."
                                    ),
                                )
                        else:
                            self.emit(type="error", msg=str(e))
                self._teardown(kill_chrome=False)
        except Exception as e:
            self.emit(type="error", msg=f"Loi trinh duyet: {e}")

    def _poll_status(self):
        """Doc URL hien tai (khong dieu huong). Neu dang o /classroom -> bao GUI."""
        page = self._page
        if not self._page_ok(page):
            if self._browser is None:
                return
            self.emit(
                type="browser_status",
                url="",
                on_classroom=False,
                alive=False,
                hint="Trinh duyet chua mo hoac da dong. Bam nut 1.",
            )
            return
        try:
            url = page.url or ""
        except Exception:
            url = ""
        on_class = bool(re.search(r"skool\.com/[^/]+/classroom/?(\?|$)", url or ""))
        # chi emit khi doi URL de bot spam
        if url != self._last_status_url:
            self._last_status_url = url
            hint = (
                "✓ Dang o Classroom — bam nut 2 (hoac cho app tu doc danh sach)."
                if on_class
                else "Trong Chrome: dang nhap → chon community → tab Classroom. KHONG dong cua so Chrome."
            )
            self.emit(
                type="browser_status",
                url=url,
                on_classroom=on_class,
                alive=True,
                hint=hint,
            )
            # Tu dong lay danh sach 1 lan khi vao dung Classroom
            if on_class and not self._auto_list_done:
                self._auto_list_done = True
                self.emit(
                    type="log",
                    msg="Phat hien trang Classroom — tu dong lay danh sach chuong...",
                )
                try:
                    self._do_list(from_auto=True)
                except Exception as e:
                    self._auto_list_done = False  # cho thu lai
                    if _is_closed_err(e):
                        raise
                    self.emit(type="log", msg=f"Tu-list loi: {e}")

    def _kill_orphan_chrome(self):
        """Giet Chrome dang giu profile .browser nhung mat CDP (nguyen nhan thuong gap)."""
        try:
            out = subprocess.check_output(
                ["pgrep", "-f", r"user-data-dir=.*/(app/)?\.browser"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            pids = [x for x in out.strip().split() if x.isdigit()]
        except Exception:
            pids = []
        for pid in pids:
            try:
                subprocess.run(["kill", "-9", pid], check=False)
            except Exception:
                pass
        # go singleton locks
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            p = USER_DATA / name
            try:
                if p.exists() or p.is_symlink():
                    p.unlink()
            except Exception:
                pass
        if pids:
            time.sleep(0.6)

    def _teardown(self, kill_chrome=False):
        self._page = None
        ctx, br = self._ctx, self._browser
        self._ctx = None
        self._browser = None
        for obj, meth in ((ctx, "close"), (br, "close")):
            if obj is None:
                continue
            try:
                getattr(obj, meth)()
            except Exception:
                pass
        if kill_chrome:
            self._kill_orphan_chrome()

    def _save_state(self):
        if not self._ctx:
            return
        try:
            self._ctx.storage_state(path=str(STATE_FILE))
        except Exception:
            pass

    def _launch(self):
        """Mo browser moi + context (load cookies neu co)."""
        self._teardown(kill_chrome=True)
        self.emit(type="log", msg="Dang mo Chromium...")
        assert self._p is not None
        self._browser = self._p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        kwargs = {
            "viewport": {"width": 1280, "height": 860},
            "locale": "en-US",
        }
        if STATE_FILE.exists() and STATE_FILE.stat().st_size > 10:
            kwargs["storage_state"] = str(STATE_FILE)
            self.emit(type="log", msg="Da nap phien dang nhap da luu.")
        self._ctx = self._browser.new_context(**kwargs)
        self._page = self._ctx.new_page()
        self._page.set_default_timeout(45000)
        return self._page

    def _page_ok(self, page) -> bool:
        if page is None:
            return False
        try:
            if page.is_closed():
                return False
            page.evaluate("1+1")
            return True
        except Exception:
            return False

    def _get_page(self):
        """Tra ve page song; relaunch neu can."""
        if self._page_ok(self._page):
            return self._page
        # thu page khac trong context
        if self._ctx is not None:
            try:
                for p in self._ctx.pages:
                    if self._page_ok(p):
                        self._page = p
                        return p
            except Exception:
                pass
        return self._launch()

    def _goto(self, page, url: str, timeout: int = 60000):
        last = None
        for attempt in range(3):
            try:
                page = self._get_page() if attempt else page
                if not self._page_ok(page):
                    page = self._launch()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                self._page = page
                return page
            except Exception as e:
                last = e
                if _is_closed_err(e) or attempt < 2:
                    self.emit(type="log", msg=f"Goto that bai (lan {attempt+1}): {e}")
                    self._teardown(kill_chrome=True)
                    page = self._launch()
                    time.sleep(0.4)
                    continue
                raise
        raise RuntimeError(f"Khong goto duoc {url}: {last}")

    def _eval(self, page, js: str):
        last = None
        for attempt in range(3):
            try:
                page = self._get_page() if attempt else page
                if not self._page_ok(page):
                    page = self._get_page()
                return page.evaluate(js)
            except Exception as e:
                last = e
                if _is_closed_err(e) and attempt < 2:
                    self.emit(type="log", msg="Evaluate that bai — mo lai trinh duyet...")
                    # giu URL neu duoc
                    url = None
                    try:
                        url = page.url if page and not page.is_closed() else None
                    except Exception:
                        url = None
                    self._teardown(kill_chrome=True)
                    page = self._launch()
                    if url and "skool.com" in (url or ""):
                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        except Exception:
                            pass
                    continue
                raise
        raise RuntimeError(f"evaluate failed: {last}")

    # ---------- commands ----------
    def _handle(self, cmd):
        t = cmd["type"]
        if t == "open":
            self._do_open()
        elif t == "open_course":
            self._do_open_course(cmd.get("url") or "")
        elif t == "list":
            self._do_list()
        elif t == "dump":
            self._do_dump(cmd)

    def _do_open(self):
        self._auto_list_done = False
        self._last_status_url = ""
        page = self._get_page()
        self.emit(
            type="log",
            msg=(
                "✓ Cua so Chrome se GIU MO (khong tu dong dong).\n"
                "Trong Chrome: (1) dang nhap  (2) vao dung community/khoa  "
                "(3) bam tab Classroom — URL .../ten-khoa/classroom\n"
                "Roi bam nut 2 trong app (hoac doi app tu doc khi thay Classroom)."
            ),
        )
        try:
            cur = page.url if self._page_ok(page) else ""
        except Exception:
            cur = ""
        if "skool.com" not in (cur or ""):
            page = self._goto(page, "https://www.skool.com/")
        try:
            page.bring_to_front()
        except Exception:
            pass
        self._save_state()
        self.emit(type="opened")
        self.emit(
            type="browser_status",
            url=page.url if self._page_ok(page) else "",
            on_classroom=False,
            alive=True,
            hint="Chrome dang mo — KHONG dong. Vao Classroom cua khoa, roi bam nut 2.",
        )

    def _do_open_course(self, url: str):
        """Mo Chrome, toi Classroom URL (user login neu can), tu-list chuong."""
        self._auto_list_done = False
        self._last_status_url = ""
        page = self._get_page()
        target = (url or "").strip()
        if not target:
            target = "https://www.skool.com/"
        # chuan hoa ve /classroom neu chi co slug
        m = re.search(r"skool\.com/([^/?#]+)", target)
        if m and "/classroom" not in target:
            target = f"https://www.skool.com/{m.group(1)}/classroom"
        self.emit(
            type="log",
            msg=(
                f"✓ Mo khoa: {target}\n"
                "Neu chua login: dang nhap trong cua so Chrome (giu mo).\n"
                "App se tu doc danh sach chuong khi vao Classroom."
            ),
        )
        page = self._goto(page, target, timeout=90000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass
        time.sleep(1.2)
        try:
            page.bring_to_front()
        except Exception:
            pass
        self._save_state()
        self.emit(type="opened")
        try:
            cur = page.url if self._page_ok(page) else target
        except Exception:
            cur = target
        on_class = bool(re.search(r"skool\.com/[^/]+/classroom", cur or ""))
        self.emit(
            type="browser_status",
            url=cur,
            on_classroom=on_class,
            alive=True,
            hint=(
                "✓ Classroom — dang lay danh sach chuong…"
                if on_class
                else "Dang nhap Skool trong Chrome neu can, roi doi / bam nut 2."
            ),
        )
        # thu list ngay
        if on_class or m:
            try:
                if not on_class and m:
                    page = self._goto(
                        page, f"https://www.skool.com/{m.group(1)}/classroom", timeout=90000
                    )
                    time.sleep(1.0)
                self._do_list(from_auto=True)
                self._auto_list_done = True
            except Exception as e:
                self._auto_list_done = False
                self.emit(type="log", msg=f"Chua lay duoc chuong (login?): {e}")

    def _do_list(self, from_auto=False):
        page = self._get_page()
        try:
            cur = page.url if self._page_ok(page) else ""
        except Exception:
            cur = ""
            page = self._get_page()
            cur = page.url or ""

        skip = {"", "settings", "@me", "discovery", "signin", "signup", "www"}
        m = re.search(r"skool\.com/([^/?#]+)", cur or "")
        if m and m.group(1) not in skip:
            grp = m.group(1)
            self.emit(type="log", msg=f"Dang mo Classroom cua «{grp}»...")
            page = self._goto(page, f"https://www.skool.com/{grp}/classroom")
            # cho Next.js hydrate
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(1.5)
            try:
                page.wait_for_function(
                    """() => {
                      try {
                        const el = document.getElementById('__NEXT_DATA__');
                        if (!el) return !!document.querySelector('a[href*="/classroom/"]');
                        const d = JSON.parse(el.textContent);
                        const pp = (d.props && d.props.pageProps) || {};
                        return !!(pp.allCourses || pp.courses || pp.classroomCourses
                          || document.querySelector('a[href*="/classroom/"]'));
                      } catch (e) { return false; }
                    }""",
                    timeout=20000,
                )
            except Exception:
                self.emit(
                    type="log",
                    msg="Cho allCourses timeout — van thu doc DOM/JSON...",
                )
                time.sleep(1.0)
        else:
            self.emit(
                type="log",
                msg=(
                    "Chua o trang community. Trong Chromium hay mo: "
                    "skool.com/<ten-khoa>/classroom  roi bam nut 2 lai."
                ),
            )

        data = self._eval(page, JS_LIST)
        self._save_state()

        if not data or not data.get("chapters"):
            try:
                url_now = self._get_page().url
            except Exception:
                url_now = cur or "?"
            self.emit(
                type="need_classroom",
                msg=(
                    "Chua thay danh sach chuong.\n\n"
                    "1) Trong cua so Chromium: dang nhap Skool\n"
                    "2) Vao community → tab Classroom\n"
                    "   URL dung: https://www.skool.com/<ten-khoa>/classroom\n"
                    "3) Bam lai «2. Lay danh sach»\n\n"
                    f"URL hien tai: {url_now}"
                ),
            )
            return

        self.group = data.get("group") or ""
        chs = data["chapters"]
        self.emit(type="log", msg=f"Tim thay {len(chs)} chuong (group={self.group}).")
        self.emit(type="chapters", group=self.group, chapters=chs)

    def _do_dump(self, cmd):
        page = self._get_page()
        chapters = cmd["chapters"]
        out = Path(cmd["out_dir"])
        all_titles = cmd.get("all_titles")
        out.mkdir(parents=True, exist_ok=True)
        order_titles = all_titles if all_titles else [c["title"] for c in chapters]
        (out / "_chapters.json").write_text(
            json.dumps(order_titles, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        pos = {t: i + 1 for i, t in enumerate(order_titles)}
        try:
            grp = self.group or (page.url or "").split("/")[3]
        except Exception:
            grp = self.group or ""
        ok = 0
        for idx, c in enumerate(chapters, 1):
            self.emit(type="dump_progress", i=idx, n=len(chapters), title=c["title"])
            try:
                page = self._goto(
                    page, f"https://www.skool.com/{grp}/classroom/{c['id']}"
                )
                try:
                    page.wait_for_function(
                        "() => { try { const d=JSON.parse(document.getElementById('__NEXT_DATA__').textContent);"
                        " return !!(d.props.pageProps.course && d.props.pageProps.course.children);} catch(e){return false;} }",
                        timeout=25000,
                    )
                except Exception:
                    time.sleep(1.5)
                page.set_default_timeout(150000)
                res = self._eval(page, JS_DUMP)
                if not res or not res.get("ok"):
                    self.emit(
                        type="log",
                        msg=f"  [bo qua] {c['title']}: {res.get('err') if res else 'loi'}",
                    )
                    continue
                n = pos.get(c["title"]) or pos.get(res["chapter"]) or idx
                safe = f"{n:02d}_{san_file(res['chapter'])}"
                (out / f"vid__{safe}.json").write_text(res["vid"], encoding="utf-8")
                (out / f"meta__{safe}.json").write_text(res["meta"], encoding="utf-8")
                ok += 1
                wv = res.get("with_video")
                if wv is None:
                    wv = (res.get("native") or 0) + (res.get("ext") or 0)
                self.emit(
                    type="log",
                    msg=(
                        f"  [OK] {res['chapter']}: {res['total']} bai "
                        f"(có video={wv}: native={res['native']} ext={res['ext']} · "
                        f"text/tài liệu={res['none']})"
                    ),
                )
                self._save_state()
            except Exception as e:
                s = str(e).lower()
                if "timeout" in s or "exceeded" in s:
                    self.emit(
                        type="log",
                        msg=f"  [bo qua] {c['title']}: timeout (chuong khoa/rong?)",
                    )
                else:
                    self.emit(type="log", msg=f"  [LOI] {c['title']}: {e}")
                if _is_closed_err(e):
                    self._teardown(kill_chrome=True)
                    page = self._launch()
        self.emit(type="dumped", ok=ok, total=len(chapters), out_dir=str(out))
