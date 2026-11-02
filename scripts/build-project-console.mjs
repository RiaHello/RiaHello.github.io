import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// --root is only for an isolated fixture; no business code is imported or executed.
const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--root')) throw new Error('Usage: node scripts/build-project-console.mjs [--root <fixture>]');
const root = args.length ? resolve(args[1]) : resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = resolve(root, 'docs/project-console.html');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const allowedSources = new Set(['src/App.vue', 'src/components/Home_Menu.vue', 'src/components/ContactPortrait.vue', 'src/components/PageTransition.vue', 'src/components/TextPressure.vue', 'src/components/ResumeAssistant.vue', 'src/lib/resume-chat.js', 'backend/app/main.py', 'backend/app/services/ai_client.py', 'backend/app/services/rate_limiter.py', 'backend/app/prompts/resume_assistant.txt']);
const style = `:root{font-family:ui-sans-serif,system-ui,-apple-system,"PingFang SC",sans-serif;color:#202a27;background:#f6f7f3;line-height:1.7}*{box-sizing:border-box}body{margin:0}a{color:#27664c;text-underline-offset:4px}button,textarea{font:inherit}button{cursor:pointer;padding:7px 12px;border:1px solid #aabcb0;border-radius:6px;background:white;color:#24583f}a:focus-visible,button:focus-visible,summary:focus-visible,textarea:focus-visible{outline:3px solid #25814f;outline-offset:3px}.layout{display:grid;grid-template-columns:240px minmax(0,1fr);max-width:1300px;margin:auto}aside{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:38px 24px;border-right:1px solid #dce3d9}aside strong{font-size:20px}nav{display:grid;gap:8px;margin-top:28px}nav a{display:block;padding:8px 10px;border-radius:5px;text-decoration:none}nav a:hover{background:#e3eadf}nav small{display:block;padding:3px 10px 8px;color:#667569}main{min-width:0;padding:40px 48px 80px}h1{font-size:32px;line-height:1.3;margin:8px 0 16px}h2{font-size:25px;margin:40px 0 8px}h3{font-size:18px;margin:0 0 10px}h4{font-size:14px;margin:20px 0 5px}p{margin:8px 0}section,article,details{scroll-margin-top:20px}article{background:white;border:1px solid #dce3d9;border-radius:9px;padding:23px;margin:20px 0}details{border-top:1px solid #e3e8df;margin-top:16px;padding-top:12px}summary{cursor:pointer;color:#345f47;font-weight:600}details[open]>summary{margin-bottom:13px}.muted{color:#657066;font-size:13px}.badge{display:inline-block;padding:3px 8px;background:#e6f1e8;color:#285d3d;border-radius:4px;font-size:12px}.warn{background:#fff0cd;color:#795800}.notice{border-left:3px solid #a3b8a7;padding:10px 16px;background:#edf1e8}.notice.warn{border-color:#aa7e28}dl{margin:10px 0;display:grid;grid-template-columns:70px minmax(0,1fr);gap:5px 15px}dt{color:#67766a}dd{margin:0}ol,ul{padding-left:23px}li{margin:8px 0}.branch{color:#6e6351;font-size:13px}.refs{display:flex;flex-wrap:wrap;gap:8px 18px}code{font-size:12px;background:#f1f4ee;padding:2px 5px;border-radius:4px}code,p,dd,li,td,textarea{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dce3d9;padding:8px;text-align:left;vertical-align:top}th{background:#edf1e8}.source{background:#f7f9f3;padding:13px;margin:10px 0;border-radius:6px}.source p{font-size:12px}.source textarea{display:block;width:100%;margin-top:8px;padding:8px;resize:vertical}.source textarea[hidden]{display:none}.source button{font-size:12px}.eyebrow{font-size:11px;letter-spacing:2px;color:#607565}.source-status{font-size:12px}footer{margin-top:40px;color:#6b7568;font-size:12px}@media(max-width:700px){.layout{display:block}aside{height:auto;position:relative;padding:20px;border-right:0;border-bottom:1px solid #dce3d9}nav{display:flex;flex-wrap:wrap;gap:2px;margin-top:12px}nav small{display:none}nav a{padding:6px 9px;font-size:13px}main{padding:24px 18px 50px}h1{font-size:27px}h2{font-size:22px}article{padding:17px}dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:7px}table,tbody,tr,td{display:block}thead{display:none}td{border-top:0}td:first-child{border-top:1px solid #dce3d9;background:#edf1e8}td:before{content:attr(data-label)"：";font-weight:600}}`;
const shell = (title, content, sidebar = '') => `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>${style}</style></head><body><div class="layout"><aside><strong>RIA / 实现说明</strong>${sidebar}</aside><main>${content}</main></div></body></html>`;

try {
  const data = JSON.parse(await readFile(resolve(root, 'docs/project-map.json'), 'utf8'));
  if (data.version !== 1 || !Array.isArray(data.pages) || !Array.isArray(data.modules) || !Array.isArray(data.apis) || !Array.isArray(data.sources)) throw new Error('Required data collections are missing');
  const allIds = new Set();
  const register = item => {
    if (!/^[a-z][a-z0-9-]*$/.test(item.id) || allIds.has(item.id)) throw new Error('Invalid or duplicate id');
    allIds.add(item.id);
  };
  for (const item of [...data.pages, ...data.modules, ...data.apis]) register(item);
  for (const page of data.pages) {
    if (!Array.isArray(page.features) || !page.name || !page.route || !page.purpose) throw new Error('Invalid page record');
    for (const feature of page.features) {
      register(feature);
      if (!Array.isArray(feature.flow) || !Array.isArray(feature.module_ids) || !Array.isArray(feature.api_ids)) throw new Error('Invalid feature record');
    }
  }
  const sources = new Map();
  for (const source of data.sources) {
    if (!/^[a-z][a-z0-9-]*$/.test(source.id) || sources.has(source.id) || !allowedSources.has(source.path) || !/^[a-f0-9]{64}$/.test(source.sha256)) throw new Error('Invalid source record');
    let actual = null;
    try { actual = createHash('sha256').update(await readFile(resolve(root, source.path))).digest('hex'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    sources.set(source.id, { ...source, actual, state: actual === source.sha256 ? '源码已核对' : actual ? '来源已变化，待复核' : '来源缺失，待复核' });
  }
  const checkRefs = refs => {
    if (!Array.isArray(refs) || !refs.length) throw new Error('Source references are missing');
    for (const ref of refs) if (!sources.has(ref.id) || !Number.isInteger(ref.line) || ref.line < 1 || typeof ref.symbol !== 'string') throw new Error('Invalid source reference');
  };
  const items = [...data.pages.flatMap(p => p.features), ...data.modules, ...data.apis];
  for (const item of items) {
    checkRefs(item.sources);
    if (item.algorithm && typeof item.algorithm === 'object') {
      const algorithm = item.algorithm;
      checkRefs(algorithm.sources);
      for (const key of ['steps', 'branches', 'parameters', 'failures']) if (!Array.isArray(algorithm[key])) throw new Error('Invalid algorithm record');
    }
    for (const id of item.module_ids || []) if (!data.modules.some(m => m.id === id)) throw new Error('Unknown module reference');
    for (const id of item.api_ids || []) if (!data.apis.some(a => a.id === id)) throw new Error('Unknown API reference');
  }
  const stale = [...sources.values()].filter(s => s.state !== '源码已核对');
  const status = refs => refs.some(ref => sources.get(ref.id).state !== '源码已核对') ? '<span class="badge warn">来源已变化或缺失 · 待复核</span>' : '<span class="badge">源码已核对 · 指纹一致</span>';
  const list = entries => `<ul>${entries.map(value => `<li>${escape(value)}</li>`).join('')}</ul>`;
  const refs = entries => entries.map(ref => {
    const source = sources.get(ref.id);
    const path = `${source.path}:${ref.line}`;
    return `<div class="source"><p><code>${escape(path)}</code></p><p>定位：${escape(ref.symbol)}</p><p class="source-status">${escape(source.state)}</p><p>核对 SHA-256：<code>${escape(source.sha256)}</code></p><p>当前 SHA-256：<code>${escape(source.actual || '文件缺失')}</code></p><button type="button" data-copy="${escape(path)}">复制来源路径</button><p role="status" aria-live="polite"></p><textarea hidden readonly aria-label="手动复制来源路径"></textarea></div>`;
  }).join('');
  const sourceDetails = entries => `<details><summary>查看实现来源与指纹</summary>${refs(entries)}</details>`;
  const links = (ids, collection) => ids.map(id => `<a href="#${id}">${escape(collection.find(x => x.id === id).name)}</a>`).join('');
  const algorithmHtml = a => `<p><strong>处理对象：</strong>${escape(a.subject)}</p><ol>${a.steps.map(step => `<li>${escape(step)}</li>`).join('')}</ol><h4>条件分支</h4>${list(a.branches)}<h4>参数与影响</h4><table><thead><tr><th>参数</th><th>取值 / 性质</th><th>位置 / 影响</th></tr></thead><tbody>${a.parameters.map(p => `<tr><td data-label="参数">${escape(p.key)}</td><td data-label="取值">${escape(p.value)}<br>${escape(p.value_kind)}</td><td data-label="位置与影响">${escape(p.location)}<br>${escape(p.impact)}</td></tr>`).join('')}</tbody></table><p><strong>结果选择：</strong>${escape(a.selection)}</p><h4>失败与清理</h4>${list(a.failures)}${sourceDetails(a.sources)}`;
  const featureHtml = f => `<article id="${f.id}"><h3>${escape(f.name)}</h3>${status(f.sources)}<dl><dt>触发</dt><dd>${escape(f.trigger)}</dd><dt>输入</dt><dd>${escape(f.input)}</dd><dt>结果</dt><dd>${escape(f.output)}</dd></dl><ol>${f.flow.map(step => `<li><strong>${escape(step.actor)}</strong>：${escape(step.action)}${step.data ? `<br><span class="muted">数据：${escape(step.data)}</span>` : ''}${step.branch ? `<br><span class="branch">分支：${escape(step.branch)}</span>` : ''}</li>`).join('')}</ol><details><summary>技术流程与接口</summary><p class="muted">下列链接说明本功能涉及的组件、接口与处理流程。</p><div class="refs">${links(f.module_ids, data.modules)}${links(f.api_ids, data.apis)}</div></details>${sourceDetails(f.sources)}</article>`;
  const sidebar = `<nav aria-label="页面功能导航">${data.pages.map(p => `<div><a href="#${p.id}">${escape(p.name)}</a><small>${escape(p.route)}</small></div>`).join('')}<a href="#shared">共享实现</a><a href="#interfaces">接口与服务</a></nav>`;
  const script = `<script>
  function revealTarget(){const target=document.getElementById(location.hash.slice(1));if(!target)return;let node=target;while(node){if(node.tagName==='DETAILS')node.open=true;node=node.parentElement;}target.scrollIntoView({block:'start'});}
  window.addEventListener('hashchange',revealTarget);revealTarget();
  document.addEventListener('click',async event=>{const button=event.target.closest('button[data-copy]');if(!button)return;const container=button.closest('.source');const message=container.querySelector('[role="status"]');const field=container.querySelector('textarea');field.hidden=true;message.textContent='正在复制…';try{if(!navigator.clipboard?.writeText)throw new Error('Unavailable');await navigator.clipboard.writeText(button.dataset.copy);message.textContent='来源路径已复制';}catch{message.textContent='无法自动复制，请手动复制下方路径。';field.value=button.dataset.copy;field.hidden=false;field.focus();field.select();}});
  </script>`;
  const header = `<p class="eyebrow">PAGE / FEATURE / IMPLEMENTATION</p><h1>${escape(data.title)}</h1><p class="notice">${escape(data.review_boundary)}</p><p class="muted">人工核对日期：${escape(data.reviewed_at)} · 本次生成：${escape(new Date().toISOString())}</p>${stale.length ? `<p class="notice warn">待复核：${stale.map(s => `${escape(s.path)}（${escape(s.state)}）`).join('；')}。以下人工流程与参数可能过期，不能作为当前实现结论。</p>` : ''}`;
  const pagesHtml = data.pages.map(p => `<section id="${p.id}"><h2>${escape(p.name)} <code>${escape(p.route)}</code></h2><p>${escape(p.purpose)}</p>${p.features.map(featureHtml).join('')}</section>`).join('');
  const modulesHtml = `<section id="shared"><h2>共享实现</h2><p class="muted">同一实现只说明一次，功能卡片通过链接引用。以下包括前端组件、Python API 服务和固定提示词模型调用。</p>${data.modules.map(m => `<article id="${m.id}"><h3>${escape(m.name)}</h3>${status(m.sources)}<p>${escape(m.responsibility)}</p><dl><dt>类型</dt><dd>${escape(m.kind)}</dd><dt>输入</dt><dd>${escape(m.input)}</dd><dt>输出</dt><dd>${escape(m.output)}</dd></dl><details><summary>展开算法、参数与异常</summary>${status(m.algorithm.sources)}${algorithmHtml(m.algorithm)}</details></article>`).join('')}</section>`;
  const apiHtml = `<section id="interfaces"><h2>接口与外部服务</h2><p>包含浏览器原生能力、静态资源、外部链接，以及新增的简历问答 JSON/SSE 后端接口。</p>${data.apis.map(a => `<article id="${a.id}"><h3>${escape(a.name)}</h3>${status(a.sources)}<dl><dt>调用</dt><dd>${escape(a.method)}</dd><dt>地址</dt><dd>${escape(a.url)}</dd><dt>输入</dt><dd>${escape(a.request)}</dd><dt>响应</dt><dd>${escape(a.response)}</dd></dl><details><summary>处理与来源</summary><p>${escape(a.algorithm)}</p><div class="refs">${links(a.module_ids, data.modules)}</div>${sourceDetails(a.sources)}</details></article>`).join('')}</section>`;
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, shell(data.title, header + pagesHtml + modulesHtml + apiHtml + '<footer>独立说明页，不连接主站导航。刷新只更新指纹对照与本页；人工说明需要定向重新核对。</footer>' + script, sidebar));
  console.log(stale.length ? `待复核：${stale.length} 个来源变化或缺失；核对基线未更新。` : '生成完成：全部来源指纹一致；未修改人工核对基线。');
  if (stale.length) process.exitCode = 2;
} catch (error) {
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, shell('说明生成失败', `<h1>说明生成失败</h1><p class="notice warn">说明数据解析、结构或来源读取失败，旧说明已停用。请修正 docs/project-map.json 后重新生成；当前没有可声明已核对的内容。</p><p>${escape(error.message)}</p>`));
  console.error(`说明生成失败：${error.message}`);
  process.exitCode = 1;
}
