"use strict";
const $ = (selector) => document.querySelector(selector);
const state = { topicId: null, sources: [], reports: [], csrf: "", busy: false };
const kindNames = {article:"论文",book:"书籍",chapter:"章节",report:"报告",standard:"标准",preprint:"预印本",web:"网页",other:"其他"};
const scopes = {metadata:"仅书目信息",abstract:"摘要",excerpt:"节选 / 网页",fulltext:"全文提取文本"};
function node(tag, text, className) { const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(className)el.className=className; return el; }
function toast(message) { const el=$("#toast"); el.textContent=message; el.hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.hidden=true,7000); }
async function api(path, body) {
  const options=body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":state.csrf},body:JSON.stringify(body)};
  const response=await fetch(path,options); const result=await response.json();
  if(!response.ok)throw new Error(result.error||"请求未完成"); return result;
}
function modelOptions() {
  const codex=$("#model-backend").value==="codex";
  $("#codex-options").hidden=!codex;$("#api-options").hidden=codex;
}
function modelStatus(status) {
  if(status.csrf)state.csrf=status.csrf;
  const codex=status.llm_backend==="codex";
  $("#model-status").textContent=status.llm_ready?(codex?"本机 Codex · ":"模型 API · ")+status.model:(codex?"未找到 Codex CLI":"模型 API 未配置")+" · 资料功能可用";
  $("#model-status").classList.toggle("warn",!status.llm_ready);
  $("#model-backend").value=status.llm_backend;$("#codex-model").value=status.codex_model;
  $("#codex-detected").textContent=status.codex_available?"已找到 Codex CLI；可测试登录与实际调用。":"未找到 Codex 可执行文件。安装官方 CLI，或在 .env 中设置 CODEX_COMMAND 为 codex.exe 的完整路径后重启。";
  $("#api-configured").textContent=status.api_ready?"API 已配置 · "+status.api_model:"API 尚未配置；可以先使用本机 Codex。";
  modelOptions();
}
async function saveModel() {
  const status=await api("/api/model-settings",Object.fromEntries(new FormData($("#model-form"))));
  modelStatus(status);
}
function tab(name) {
  document.querySelectorAll("[data-tab]").forEach(b=>{const active=b.dataset.tab===name;b.classList.toggle("active",active);b.setAttribute("aria-selected",String(active));});
  ["library","reports","qa"].forEach(t=>$("#panel-"+t).hidden=t!==name);
}
async function refreshTopics() {
  const topics=await api("/api/topics"), list=$("#topics"); list.replaceChildren();
  topics.forEach(t=>{const b=node("button",undefined,"topic-button"+(t.id===state.topicId?" active":""));b.append(node("span",t.name),node("small",String(t.source_count)));b.onclick=()=>loadTopic(t.id).catch(e=>toast(e.message));list.append(b);});
  if(!topics.length)list.append(node("p","还没有主题。点击 ＋ 开始整理。","sidebar-empty"));
  return topics;
}
async function loadTopic(id) {
  const changed=state.topicId!==id;
  const result=await api("/api/topics/"+id); state.topicId=id; state.sources=result.sources; state.reports=result.reports;
  localStorage.setItem("research-topic",String(id));
  $("#welcome").hidden=true;$("#workspace").hidden=false;$("#topic-name").textContent=result.topic.name;$("#topic-query").textContent="检索词："+result.topic.query;
  $("#count-all").textContent=state.sources.length;$("#count-content").textContent=state.sources.filter(s=>s.text_length&&!s.excluded).length;
  $("#count-unverified").textContent=state.sources.filter(s=>!s.verified).length;$("#count-reports").replaceChildren(document.createTextNode(String(state.reports.length)),node("span","/ 2"));
  $("#export-xlsx").href=`/api/topics/${id}/export?format=xlsx`;$("#export-zip").href=`/api/topics/${id}/export?format=zip`;
  renderScreening(result.last_search);
  if(changed){$("#filter").value="";$("#report-content").replaceChildren();$("#report-state").hidden=true;$("#answer").replaceChildren();$("#evidence").replaceChildren();$("#question").value="";tab("library");}
  renderSources();await refreshTopics();
}
function renderScreening(search) {
  $("#screening-summary").hidden=!search?.heat;
  if(!search?.heat)return;
  const heat=search.heat;
  $("#screening-title").textContent=`最近筛选 · 候选集热度${heat.label} · ${heat.window} 年相关研究 ${heat.recent_count} 条`;
  const details=$("#screening-details");details.replaceChildren(node("p",heat.basis));
  if(search.queries)details.append(node("p","实际检索式："+search.queries.join("；")));
  Object.entries(search.policies||{}).forEach(([name,p])=>{
    const threshold=p.annual_citation_threshold===null?"无引用门槛":`年均引用估值 ≥ ${p.annual_citation_threshold.toFixed(2)}（本来源 P${p.percentile} 与最低门槛取较高者）`;
    const counts=search.counts[name];
    details.append(node("p",`${name}：${p.mode_label}，${counts.returned} 条候选 → ${p.selected} 条入选；${threshold}。${p.rule}`));
  });
  (search.warnings||[]).forEach(w=>details.append(node("p",w)));
  details.append(node("p",search.note));
  const link=node("a","下载本次完整筛选记录（含未入选候选） ↓");link.href=`/files/${state.topicId}/${search.audit_file}`;details.append(link);
}
function renderSources() {
  const query=$("#filter").value.toLowerCase(); const sources=state.sources.filter(s=>[s.title,s.title_zh,s.title_en,s.authors,s.venue].join(" ").toLowerCase().includes(query));
  const order=$("#source-sort").value;
  sources.sort((a,b)=>Number(a.excluded)-Number(b.excluded)||(order==="year"?Number(b.year||0)-Number(a.year||0):order==="if"?(b.journal_metrics?.value??-1)-(a.journal_metrics?.value??-1):(a.importance?.rank??999999)-(b.importance?.rank??999999)));
  const body=$("#source-rows");body.replaceChildren();
  for(const s of sources){
    const row=node("tr"), first=node("td"), title=node("button",s.title_zh||s.title,"source-title");title.onclick=()=>openSource(s.id).catch(e=>toast(e.message));
    if(s.importance?.rank){const rank=node("div",`#${s.importance.rank} · 重要度 ${s.importance.score}`,"priority-label");rank.title=s.importance.reason;first.append(rank);}first.append(title);
    if(s.title_zh&&s.title_zh!==s.title)first.append(node("div",s.title,"source-subtitle"));
    first.append(node("div",`${kindNames[s.kind]||s.kind} · ${s.authors||"作者未提供"}`,"source-subtitle"));
    if(s.summary)first.append(node("div",s.summary,"source-note"));
    const second=node("td");second.append(node("div",s.venue||"来源未提供"),node("div",s.year||"年份未提供","source-subtitle"));
    if(s.citation_metrics)second.append(node("div",`引用 ${s.citation_metrics.count??"未提供"} · ${s.citation_metrics.provider}`,"source-subtitle"));
    if(s.journal_metrics){const m=s.journal_metrics;second.append(node("div",m.value==null?`IF ${m.status}`:`IF ${m.value} · ${m.year}`,"if-label"));}
    const scope=node("td");scope.append(node("span",scopes[s.evidence_level],"badge"+(s.evidence_level==="metadata"?" warn":"")));
    const status=node("td");status.append(node("div",s.verified?"已核验":"待核验",s.verified?"":"muted"));if(s.excluded)status.append(node("div","已排除","source-subtitle"));if(s.ai_stale)status.append(node("div","AI 整理已过期","source-subtitle"));
    if(s.screening){const label=node("div",s.screening.path,"source-subtitle");label.title=s.screening.reason;status.append(label);}
    row.append(first,second,scope,status);body.append(row);
  }
  $("#library-empty").hidden=!!sources.length;$(".table-wrap").hidden=!sources.length;
  $("#library-empty h3").textContent=state.sources.length?"没有匹配的资料":"把第一份资料放进来";
}
function citeText(parent,text) {
  const re=/\[(S[a-f0-9]{12})(?::C(\d+))?\]/g;let start=0,match;
  while((match=re.exec(text))){parent.append(document.createTextNode(text.slice(start,match.index)));const b=node("button",match[0],"citation");const id=match[1];b.onclick=()=>openSource(id).catch(e=>toast(e.message));parent.append(b);start=re.lastIndex;}
  parent.append(document.createTextNode(text.slice(start)));
}
function markdown(container,text) {
  container.replaceChildren();
  text.split("\n").forEach(line=>{if(!line.trim())return;let tag="p";let content=line;
    const heading=/^(#{1,3})\s+(.*)/.exec(line);if(heading){tag="h"+heading[1].length;content=heading[2];}
    else if(line.startsWith("> ")){tag="blockquote";content=line.slice(2);}
    else if(/^[-*] /.test(line))content="• "+line.slice(2);
    const el=node(tag);citeText(el,content);container.append(el);
  });
}
function showReport(kind) {
  const report=state.reports.find(r=>r.kind===kind);tab("reports");
  if(!report){toast("还没有这份报告，请先生成。");return;}
  markdown($("#report-content"),report.content);$("#report-state").hidden=!report.stale;
  $("#report-state").textContent="资料已更新，这份报告依据旧版本资料生成，请重新生成。";
}
async function task(path,body,onDone) {
  if(state.busy){toast("已有任务正在运行，请等待当前任务结束。");return;}
  state.busy=true;document.body.classList.add("is-busy");const topicId=state.topicId;
  $("#task").hidden=false;$("#task").classList.remove("error");$("#task-message").textContent="正在开始任务…";$("#task-details").replaceChildren();$("#dismiss-task").hidden=true;
  try{
    const {job_id}=await api(path,body);let job;
    do{await new Promise(resolve=>setTimeout(resolve,1200));job=await api("/api/jobs/"+job_id);$("#task-message").textContent=job.message;}while(job.state==="running");
    if(job.state==="error")throw new Error(job.message);
    const result=job.result||{};
    if(result.counts)Object.entries(result.counts).forEach(([name,c])=>$("#task-details").append(node("div",c.error?`${name}：失败，${c.error}`:`${name}：${c.returned} 条候选，入选 ${c.selected}，新增 ${c.added}，合并 ${c.merged}`)));
    if(result.updated!==undefined)$("#task-details").append(node("div",`已整理 ${result.updated} 条资料`));
    (result.warnings||[]).forEach(w=>$("#task-details").append(node("div",w)));
    if(result.note)$("#task-details").append(node("div",result.note));
    if(state.topicId===topicId){await loadTopic(topicId);if(onDone)await onDone(result);}
    else await refreshTopics();
  }catch(e){$("#task-message").textContent=e.message;$("#task").classList.add("error");}
  finally{state.busy=false;document.body.classList.remove("is-busy");$("#dismiss-task").hidden=false;}
}
async function openSource(id) {
  const s=id?await api("/api/sources/"+id):{kind:"article",evidence_level:"abstract"};const form=$("#source-form");form.reset();
  for(const el of form.elements){if(!el.name)continue;if(el.type==="checkbox")el.checked=!!s[el.name];else el.value=s[el.name]||"";}
  $("#source-dialog-title").textContent=id?"资料详情与原文":"手工录入资料";
  $("#source-card").hidden=!id;$("#source-fetch").hidden=!(id&&s.url);
  if(id)$("#source-card").href=`/files/${s.topic_id}/sources/${s.id}.md`;
  $("#source-provenance").replaceChildren();
  (s.provenance||[]).forEach(p=>$("#source-provenance").append(node("div",`${p.provider} · ${p.url||"本地资料"} · ${p.retrieved_at}`)));
  if(s.original_file){const a=node("a","下载原始文件");a.href=`/files/${s.topic_id}/${s.original_file}`;$("#source-provenance").append(a);}
  if(s.ai_based_on)$("#source-provenance").append(node("div","译名及整理内容含 AI 输出，请对照原文核验。"));
  if(s.ai_stale)$("#source-provenance").append(node("div","原文或元数据已变化，上次 AI 整理内容已过期，请重新整理。"));
  if(s.citation_metrics){const m=s.citation_metrics;$("#source-provenance").append(node("div",`引用次数：${m.count??"未提供"} · ${m.provider} · ${m.retrieved_at}（不是期刊影响因子）`));}
  if(s.screening)$("#source-provenance").append(node("div",`入选依据：${s.screening.path} · ${s.screening.reason}；${s.screening.assessed_at}`));
  if(s.journal_metrics){const m=s.journal_metrics;$("#source-provenance").append(node("div",m.value==null?`期刊 IF：${m.status}`:`期刊 IF：${m.value}（${m.year}），核实日期 ${m.retrieved_at}；不是本文发表时的IF，也不是单篇论文质量分。`));if(m.source_url){const a=node("a","查看 IF 官方核实来源 ↗");a.href=m.source_url;a.target="_blank";a.rel="noopener noreferrer";$("#source-provenance").append(a);}}
  if(s.importance)$("#source-provenance").append(node("div",`阅读重要度：${s.importance.score} / 100，排名 ${s.importance.rank??"未纳入"}。${s.importance.reason}。${s.importance.rule}`));
  $("#source-dialog").showModal();
}
function showAnswer(result) {
  markdown($("#answer"),result.answer);const list=$("#evidence");list.replaceChildren();
  for(const e of result.evidence){const details=node("details",undefined,"evidence-item"), summary=node("summary",`[${e.label}] ${e.title} · ${scopes[e.evidence_level]}`);details.append(summary,node("pre",e.text));
    const b=node("button","查看资料与完整提取文本","text-button");b.onclick=()=>openSource(e.source_id).catch(err=>toast(err.message));details.append(b);
    if(e.url){const a=node("a","原始网址 ↗");a.href=e.url;a.target="_blank";a.rel="noopener noreferrer";details.append(a);}list.append(details);}
}
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>tab(b.dataset.tab));
$("#new-topic").onclick=$("#welcome-create").onclick=()=>$("#topic-dialog").showModal();
$("#settings-button").onclick=async()=>{try{modelStatus(await api("/api/status"));$("#settings-dialog").showModal();}catch(e){toast(e.message);}};
$("#model-backend").onchange=modelOptions;
$("#model-form").onsubmit=async e=>{e.preventDefault();try{await saveModel();$("#model-check-result").hidden=false;$("#model-check-result").textContent="已保存，新的 AI 任务将使用所选接入方式。";}catch(err){toast(err.message);}};
$("#test-model").onclick=async()=>{
  if(state.busy){toast("请等待当前任务结束后测试连接。");return;}
  const output=$("#model-check-result");output.hidden=false;output.textContent="正在保存并连接模型…";
  state.busy=true;$("#save-model").disabled=true;$("#test-model").disabled=true;
  try{await saveModel();const {job_id}=await api("/api/model-test",{});let job;
    do{await new Promise(resolve=>setTimeout(resolve,1200));job=await api("/api/jobs/"+job_id);output.textContent=job.message;}while(job.state==="running");
    if(job.state==="error")throw new Error(job.message);
    output.textContent=`连接成功 · ${job.result.llm_backend==="codex"?"本机 Codex":"模型 API"} · ${job.result.model}。模型回复：${job.result.answer}`;
  }catch(e){output.textContent=e.message;}
  finally{state.busy=false;$("#save-model").disabled=false;$("#test-model").disabled=false;}
};
$("#collect-button").onclick=()=>$("#collect-dialog").showModal();
$("#import-button").onclick=()=>$("#import-dialog").showModal();
$("#manual-button").onclick=()=>{$("#import-dialog").close();openSource().catch(e=>toast(e.message));};
$("#filter").oninput=renderSources;
$("#source-sort").onchange=renderSources;
$("#rank-button").onclick=()=>task(`/api/topics/${state.topicId}/rank`,{});
$("#dismiss-task").onclick=()=>$("#task").hidden=true;
$("#topic-form").onsubmit=async e=>{e.preventDefault();try{const result=await api("/api/topics",Object.fromEntries(new FormData(e.target)));$("#topic-dialog").close();e.target.reset();await loadTopic(result.id);}catch(err){toast(err.message);}};
$("#collect-form").onsubmit=e=>{e.preventDefault();const form=new FormData(e.target);const body={limit:Number(form.get("limit")),mode:form.get("mode")};$("#collect-dialog").close();task(`/api/topics/${state.topicId}/collect`,body);};
$("#url-form").onsubmit=e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));$("#import-dialog").close();task(`/api/topics/${state.topicId}/url`,body);};
$("#upload-form").onsubmit=async e=>{e.preventDefault();try{const file=$("#upload-file").files[0];if(!file||file.size>20000000)throw new Error("请选择20 MB以内的文件");
  const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=()=>reject(new Error("文件读取失败"));reader.readAsDataURL(file);});
  const body={...Object.fromEntries(new FormData(e.target)),filename:file.name,content};$("#import-dialog").close();task(`/api/topics/${state.topicId}/upload`,body);
}catch(err){toast(err.message);}};
$("#source-form").onsubmit=async e=>{e.preventDefault();const form=e.target;const body=Object.fromEntries(new FormData(form));body.verified=form.elements.verified.checked;body.excluded=form.elements.excluded.checked;
  try{await api(body.id?`/api/sources/${body.id}`:`/api/topics/${state.topicId}/sources`,body);$("#source-dialog").close();await loadTopic(state.topicId);toast("资料已保存。已有报告需根据最新资料重新生成。");}catch(err){toast(err.message);}};
$("#source-fetch").onclick=()=>{const id=$("#source-form").elements.id.value;$("#source-dialog").close();task(`/api/sources/${id}/fetch`,{});};
$("#enrich-button").onclick=()=>task(`/api/topics/${state.topicId}/enrich`,{});
document.querySelectorAll("[data-generate]").forEach(b=>b.onclick=()=>task(`/api/topics/${state.topicId}/report`,{kind:b.dataset.generate},()=>showReport(b.dataset.generate)));
document.querySelectorAll("[data-report]").forEach(b=>b.onclick=()=>showReport(b.dataset.report));
$("#ask-form").onsubmit=e=>{e.preventDefault();task(`/api/topics/${state.topicId}/ask`,{question:$("#question").value,use_ai:$("#use-ai").checked},showAnswer);};
(async()=>{try{modelStatus(await api("/api/status"));const topics=await refreshTopics();const saved=Number(localStorage.getItem("research-topic"));if(topics.length)await loadTopic(topics.some(t=>t.id===saved)?saved:topics[0].id);}catch(e){toast("连接失败："+e.message);}})();
