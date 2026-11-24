import { createClient } from "https://esm.sh/@supabase/supabase-js@2.57.0";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./supabase-config.js";

const db = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
const $ = (id) => document.getElementById(id);
const ANIMALS = ["Avestruz","Águia","Burro","Borboleta","Cachorro","Cabra","Carneiro","Camelo","Cobra","Coelho","Cavalo","Elefante","Galo","Gato","Jacaré","Leão","Macaco","Porco","Pavão","Peru","Touro","Tigre","Urso","Veado","Vaca"];
const state = {sources:[], modalities:[], groups:[], mapping:[], extractions:[], results:[], category:"top10", type:"grupo"};
const fmtDate = (d) => d ? new Date(`${d}T12:00:00`).toLocaleDateString("pt-BR") : "—";
const escapeHtml = (v="") => String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function animalFor(group){ return ANIMALS[Number(group)-1] || "—"; }
function mapGroup(dezena){ const n=Number(dezena); return n===0 ? 25 : Math.ceil(n/4); }

async function fetchAll(table, query){
  const {data,error}=await query;
  if(error) throw new Error(`${table}: ${error.message}`);
  return data || [];
}
async function loadData(){
  $("connectionText").textContent="Consultando banco";
  try{
    const [sources,modalities,groups,mapping,extractions,results]=await Promise.all([
      fetchAll("fontes",db.from("fontes_resultados_bicho").select("id,nome,uf,municipio,tipo_fonte,ativa").eq("ativa",true).order("nome")),
      fetchAll("modalidades",db.from("modalidades_bicho").select("id,codigo,nome,ativa").eq("ativa",true).order("nome")),
      fetchAll("grupos",db.from("grupos_animais_bicho").select("grupo,animal").eq("ativo",true).order("grupo")),
      fetchAll("mapa",db.from("mapeamento_dezenas_bicho").select("dezena,grupo").order("dezena")),
      fetchAll("extrações",db.from("extracoes_bicho").select("id,fonte_id,modalidade_id,data_extracao,horario_local,uf,municipio,identificador_origem,url_resultado,status_conferencia,observacoes").order("data_extracao",{ascending:false}).limit(5000)),
      fetchAll("resultados",db.from("resultados_bicho").select("id,extracao_id,posicao,numero,grupo,dezena,centena,milhar,animal").order("posicao"))
    ]);
    state.sources=sources;state.modalities=modalities;state.groups=groups;state.mapping=mapping;state.extractions=extractions;
    const validIds=new Set(extractions.map(x=>x.id));
    state.results=results.filter(r=>validIds.has(r.extracao_id));
    $("connectionText").textContent="Banco conectado";$("connectionText").parentElement.classList.add("online");
    fillFilters(); render();
  }catch(err){
    $("connectionText").textContent="Falha na conexão";
    $("insightText").textContent=`Não foi possível carregar o banco: ${err.message}. Verifique a conexão, a chave pública e as permissões de leitura (RLS).`;
    console.error(err);
  }
}
function fillFilters(){
  const add=(id,items,label)=>{const el=$(id),old=el.value;el.innerHTML=`<option value="">${label}</option>`+items.map(x=>`<option value="${escapeHtml(x.value)}">${escapeHtml(x.label)}</option>`).join("");el.value=old;};
  add("ufFilter",[...new Set([...state.sources.map(x=>x.uf),...state.extractions.map(x=>x.uf)].filter(Boolean))].sort().map(x=>({value:x,label:x})),"Todas as UFs");
  add("sourceFilter",state.sources.map(x=>({value:x.id,label:x.nome})),"Todas as fontes");
  add("modalityFilter",state.modalities.map(x=>({value:x.id,label:x.nome})),"Todas as modalidades");
}
function filtered(){
  let ex=[...state.extractions];const uf=$("ufFilter").value,source=$("sourceFilter").value,mod=$("modalityFilter").value,period=$("periodFilter").value;
  if(uf)ex=ex.filter(x=>x.uf===uf);if(source)ex=ex.filter(x=>x.fonte_id===source);if(mod)ex=ex.filter(x=>x.modalidade_id===mod);
  if(period!=="all"){const cutoff=new Date();cutoff.setDate(cutoff.getDate()-Number(period));const min=cutoff.toISOString().slice(0,10);ex=ex.filter(x=>x.data_extracao>=min);}
  const ids=new Set(ex.map(x=>x.id));return {ex,rs:state.results.filter(r=>ids.has(r.extracao_id))};
}
function countsFor(rs,type){
  const counts=new Map();
  for(const r of rs){
    let key=null;
    if(type==="grupo")key=String(r.grupo??(r.dezena?mapGroup(r.dezena):"")).padStart(2,"0");
    if(type==="dezena")key=r.dezena || (r.numero?.slice(-2));
    if(type==="centena")key=r.centena || (r.numero?.length>=3?r.numero.slice(-3):null);
    if(type==="milhar")key=r.milhar || (r.numero?.length>=4?r.numero.slice(-4):null);
    if(key!==null && key!=="" && key!=="00" || (type==="dezena"&&key==="00"))counts.set(String(key), (counts.get(String(key))||0)+1);
  }
  return [...counts.entries()].map(([key,count])=>({key,count})).sort((a,b)=>b.count-a.count||a.key.localeCompare(b.key));
}
function render(){
  const {ex,rs}=filtered();$("statDraws").textContent=ex.length.toLocaleString("pt-BR");$("statResults").textContent=rs.length.toLocaleString("pt-BR");$("statSources").textContent=state.sources.length.toLocaleString("pt-BR");
  const groupCounts=countsFor(rs,"grupo");const best=groupCounts[0];$("statGroup").textContent=best?best.key:"—";$("statAnimal").textContent=best?animalFor(best.key):"Sem dados validados";
  $("metricRecent").textContent=rs.length.toLocaleString("pt-BR");$("metricCoverage").textContent=`${groupCounts.length}/25`;
  renderBars(groupCounts);renderInsight(groupCounts,rs,ex);renderHistory(ex,rs);renderSuggestions(rs);renderAnimals();
  $("updatedAt").textContent=`Atualizado em ${new Date().toLocaleString("pt-BR")}`;
}
function renderBars(data){
  const all=Array.from({length:25},(_,i)=>({key:String(i+1).padStart(2,"0"),count:0}));data.forEach(d=>{const a=all.find(x=>x.key===d.key);if(a)a.count=d.count;});
  const max=Math.max(1,...all.map(x=>x.count));
  $("groupChart").innerHTML=all.map(x=>`<div class="bar-item"><em>${x.count||""}</em><div class="bar" style="height:${Math.max(2,x.count/max*100)}%"></div><small>${x.key}</small></div>`).join("");
}
function renderInsight(groups,rs,ex){
  if(!rs.length){$("insightText").textContent="Ainda não existem resultados coletados para os filtros selecionados. Aguarde uma execução bem-sucedida do coletor ou confira o cadastro das fontes.";return;}
  const top=groups.slice(0,3).map(x=>`${x.key} (${animalFor(x.key)})`).join(", ");
  const bottom=[...groups].sort((a,b)=>a.count-b.count).slice(0,3).map(x=>x.key).join(", ");
  $("insightText").textContent=`Foram analisados ${rs.length} resultados em ${ex.length} extrações. Os grupos com maior frequência observada são ${top||"—"}. Os menos frequentes na amostra são ${bottom||"—"}. Essa diferença descreve apenas o histórico selecionado e não indica vantagem matemática em sorteios futuros.`;
}
function renderHistory(ex,rs){
  const byId=new Map();rs.forEach(r=>{if(!byId.has(r.extracao_id))byId.set(r.extracao_id,[]);byId.get(r.extracao_id).push(r);});
  $("historyCount").textContent=`${ex.length} registros`;
  const source=new Map(state.sources.map(x=>[x.id,x.nome])),mods=new Map(state.modalities.map(x=>[x.id,x.nome]));
  $("historyBody").innerHTML=ex.slice(0,30).map(x=>{
    const nums=(byId.get(x.id)||[]).sort((a,b)=>a.posicao-b.posicao).map(r=>`${r.posicao}º ${r.numero}`).join(" · ");
    return `<tr><td>${fmtDate(x.data_extracao)}</td><td>${escapeHtml((x.horario_local||"—").slice(0,5))}</td><td>${escapeHtml([x.uf,x.municipio].filter(Boolean).join(" / ")||"Nacional")}</td><td>${escapeHtml(source.get(x.fonte_id)||"Fonte")}</td><td>${escapeHtml(mods.get(x.modalidade_id)||"—")}</td><td>${escapeHtml(x.status_conferencia||"—")}</td><td class="numbers">${escapeHtml(nums||"Sem posições")}</td></tr>`;
  }).join("")||'<tr><td colspan="7" class="empty">Nenhuma extração coletada encontrada.</td></tr>';
}
function rankData(rs,type,category){
  const all=countsFor(rs,type);if(!all.length)return [];
  const recent=rs.slice().sort((a,b)=>String(b.id).localeCompare(String(a.id))).slice(0,Math.max(1,Math.ceil(rs.length*.3)));
  const recentCounts=new Map(countsFor(recent,type).map(x=>[x.key,x.count]));
  const max=Math.max(1,...all.map(x=>x.count)),min=Math.min(...all.map(x=>x.count)),maxRecent=Math.max(1,...recentCounts.values());
  const score=(x)=>{
    const rec=(recentCounts.get(x.key)||0)/maxRecent;
    const freq=x.count/max;
    const low=1-(x.count-min)/Math.max(1,max-min);
    if(category==="menos_recorrentes")return low;
    if(category==="tendencia_recente")return rec;
    if(category==="equilibradas")return (freq+rec+low)/3;
    if(category==="alternativas")return (low+1-rec)/2;
    if(category==="adaptativa")return .45*freq+.35*rec+.2*(1-Math.abs(freq-rec));
    return .65*freq+.35*rec;
  };
  return all.map(x=>({...x,score:score(x)})).sort((a,b)=>category==="menos_recorrentes"||category==="alternativas"?b.score-a.score:b.score-a.score);
}
function renderSuggestions(rs){
  const data=rankData(rs,state.type,state.category).slice(0, state.category==="top10"?10:10);
  $("suggestionList").innerHTML=data.map((x,i)=>{
    const label=state.type==="grupo"?animalFor(x.key):state.type==="dezena"?`Grupo ${String(mapGroup(x.key)).padStart(2,"0")}`:"Ocorrências no histórico";
    const pct=Math.round(x.score*100);
    return `<article class="suggestion-card"><div class="rank">#${String(i+1).padStart(2,"0")} · ÍNDICE RELATIVO</div><strong>${escapeHtml(x.key)}</strong><small>${escapeHtml(label)}</small><small>${x.count} ocorrência(s) · ${pct}/100</small><div class="score-line"><i style="width:${pct}%"></i></div></article>`;
  }).join("")||'<div class="empty">Sem dados suficientes para calcular esta categoria.</div>';
}
function renderAnimals(){
  $("animalGrid").innerHTML=ANIMALS.map((a,i)=>{const g=i+1,start=((i*4+1)%100);const nums=[0,1,2,3].map(j=>String((i*4+j+1)%100).padStart(2,"0")).join(" · ");return `<div class="animal"><span class="num">${String(g).padStart(2,"0")}</span><div><b>${a}</b><small>${nums}</small></div></div>`;}).join("");
}
$("categoryTabs").addEventListener("click",e=>{const b=e.target.closest("[data-cat]");if(!b)return;state.category=b.dataset.cat;document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x===b));renderSuggestions(filtered().rs);});
$("typeTabs").addEventListener("click",e=>{const b=e.target.closest("[data-type]");if(!b)return;state.type=b.dataset.type;document.querySelectorAll(".type").forEach(x=>x.classList.toggle("active",x===b));renderSuggestions(filtered().rs);});
["ufFilter","sourceFilter","modalityFilter","periodFilter"].forEach(id=>$(id).addEventListener("change",render));
$("refreshBtn").addEventListener("click",loadData);$("analyzeBtn").addEventListener("click",()=>renderSuggestions(filtered().rs));
renderAnimals();loadData();
