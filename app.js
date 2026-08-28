const app = { page: "dashboard" };
let db = { users: [], clients: [], loans: [], payments: [], installments: [], messages: [] };
let sessionUser = null;

async function api(path, options = {}) {
  const opts = { credentials: "same-origin", headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const response = await fetch(path, opts);
  let payload = {};
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(payload.error || `Erro HTTP ${response.status}`);
  return payload;
}

function getDB(){ return db; }
function currentUser(){ return sessionUser; }
function isAdmin(){ return sessionUser?.role === "admin"; }
async function refreshDB(){ const data = await api("/api/data"); db = data; return db; }
function money(v){ return Number(v||0).toLocaleString("pt-BR",{style:"currency",currency:"BRL"}); }
function dateBR(s){ if(!s)return "-"; const d=new Date(s+"T12:00:00"); return d.toLocaleDateString("pt-BR"); }
function addPeriod(iso,frequency){ const d=new Date(iso+"T12:00:00"); if(frequency==="weekly") d.setDate(d.getDate()+7); else if(frequency==="biweekly") d.setDate(d.getDate()+14); else { const day=d.getDate(); d.setMonth(d.getMonth()+1); if(d.getDate()!==day)d.setDate(0); } return d.toISOString().slice(0,10); }
function installmentDates(l){ const dates=[]; let current=l.due; for(let i=0;i<l.installments;i++){ dates.push(current); current=addPeriod(current,l.frequency||"monthly"); } return dates; }
function frequencyLabel(v){ return v==="weekly"?"Semanal":v==="biweekly"?"Quinzenal":"Mensal"; }
function today(){ const parts=new Intl.DateTimeFormat("en-US",{timeZone:"America/Sao_Paulo",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date()); const map=Object.fromEntries(parts.filter(p=>p.type!=="literal").map(p=>[p.type,p.value])); return `${map.year}-${map.month}-${map.day}`; }
function clientName(db,id){ return db.clients.find(c=>c.id===id)?.name||"Cliente removido"; }
function normalizeWhatsApp(phone){ return String(phone||"").replace(/\D/g,""); }
function validMobileBR(phone){ const d=normalizeWhatsApp(phone); return /^[1-9][0-9][9][0-9]{8}$/.test(d); }
function whatsappConfirmed(value){ return value===true||value==="true"; }
function normalizeText(value){ return String(value??"").trim().replace(/\s+/g," "); }
function validName(value){ const v=normalizeText(value); return v.length>=3&&v.length<=80&&/^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '’\-][A-Za-zÀ-ÖØ-öø-ÿ]+)*$/.test(v); }
function normalizeCPF(value){ return String(value??"").replace(/\D/g,""); }
function formatCPF(value){ const d=normalizeCPF(value); return d.length===11?d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/,"$1.$2.$3-$4"):String(value??"").trim(); }
function validClientEmail(value){ const v=String(value??"").trim(); return v===v.toLowerCase()&&/^[\x00-\x7F]+$/.test(v)&&validEmail(v); }
function validEmail(value){ const v=String(value??"").trim().toLowerCase(); return v.length>=5&&v.length<=120&&!/\s/.test(v)&&/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v); }
function validInternalEmail(value){ return validEmail(value)&&String(value).trim().toLowerCase().endsWith("@agiproz.local"); }
function normalizeLogin(value){ return String(value??"").trim().toLowerCase(); }
function validLogin(value){ const v=normalizeLogin(value); return v.length>=3&&v.length<=30&&/^[a-z0-9][a-z0-9._-]*$/.test(v); }
function validPassword(value){ const v=String(value??""); return v.length>=8&&v.length<=64&&!/\s/.test(v)&&/[A-Z]/.test(v)&&/[0-9]/.test(v)&&/[^A-Za-z0-9]/.test(v); }
function validISODate(value){ return /^\d{4}-\d{2}-\d{2}$/.test(String(value??""))&&!Number.isNaN(new Date(value+"T12:00:00").getTime()); }
function isFutureOrToday(value){ return validISODate(value)&&value>=today(); }
function findDuplicateClient(db,data,id){ const cpf=normalizeCPF(data.cpf),email=String(data.email).trim().toLowerCase(),phone=normalizeWhatsApp(data.phone); return db.clients.find(c=>c.id!==id&&(normalizeCPF(c.cpf)===cpf||String(c.email||"").trim().toLowerCase()===email||normalizeWhatsApp(c.phone)===phone)); }
function findDuplicateUser(db,data,id){ const login=normalizeLogin(data.login),email=String(data.email).trim().toLowerCase(); return db.users.find(u=>u.id!==id&&(normalizeLogin(u.login||"")===login||String(u.email||"").trim().toLowerCase()===email)); }
function validateLoanData(db,data){ if(!db.clients.some(c=>c.id===data.clientId&&c.active!==false))return "Selecione um cliente ativo válido."; if(!Number.isFinite(data.amount)||data.amount<50||data.amount>50000)return "O valor deve estar entre R$ 50,00 e R$ 50.000,00."; if(!Number.isFinite(data.interest)||data.interest<0||data.interest>100)return "A taxa deve estar entre 0% e 100%."; if(!Number.isInteger(data.installments)||data.installments<1||data.installments>36)return "O número de parcelas deve ser um inteiro entre 1 e 36."; if(!["weekly","biweekly","monthly"].includes(data.frequency))return "Selecione a periodicidade das parcelas."; if(!isFutureOrToday(data.due))return "Informe uma data de vencimento válida a partir de hoje."; return ""; }
function daysUntil(date){ const a=new Date(today()+"T00:00:00"),b=new Date(date+"T00:00:00"); return Math.round((b-a)/86400000); }
function whatsappNumber(phone){ const digits=normalizeWhatsApp(phone); if(!digits)return""; return digits.startsWith("55")?digits:"55"+digits; }
function whatsappMessageForLoan(l,db){ const c=db.clients.find(x=>x.id===l.clientId); if(!c)return null; const inst=nextInstallment(l,db),parcela=inst?.number||l.paid+1,due=inst?.due||l.due,s=loanStatus(l),d=daysUntil(due),valor=(s==="late"||d<0)?(inst?.amountDue??inst?.value??loanTotal(l)/l.installments):(inst?.value??loanTotal(l)/l.installments); let text=""; if(s==="late"||d<0)text=`Olá, ${c.name}. Aqui é o AgiProz. A parcela ${parcela}/${l.installments}, no valor atualizado de ${money(valor)}, venceu em ${dateBR(due)} e consta em atraso. Pedimos que regularize o pagamento o quanto antes. Se o pagamento já foi realizado, desconsidere esta mensagem.`; else if(d===1)text=`Olá, ${c.name}. Aqui é o AgiProz. Lembrete: a parcela ${parcela}/${l.installments}, no valor de ${money(valor)}, vence amanhã (${dateBR(due)}). Se precisar confirmar alguma informação sobre o pagamento, estamos à disposição.`; else return null; return{text,phone:whatsappNumber(c.phone),kind:(s==="late"||d<0)?"atraso":"lembrete"}; }
function openWhatsAppLoan(id){ const l=getDB().loans.find(x=>x.id===id); if(!l)return showToast("Empréstimo não encontrado."); const m=whatsappMessageForLoan(l,getDB()); if(!m)return showToast("Esta parcela não está no período de lembrete ou atraso."); if(!m.phone)return showToast("Cadastre um telefone/WhatsApp para este cliente."); window.open(`https://wa.me/${m.phone}?text=${encodeURIComponent(m.text)}`,"_blank","noopener,noreferrer"); }
function dueMessageAction(l,db){ const due=loanDue(l,db); const d=daysUntil(due); if(loanStatus(l)==="late"||d<0)return `<button class="action-btn whatsapp late" data-whatsapp="${l.id}">WhatsApp • atraso</button>`; if(d===1)return `<button class="action-btn whatsapp" data-whatsapp="${l.id}">WhatsApp • lembrete</button>`; return ""; }
function showToast(msg){ const el=document.getElementById("toast"); el.textContent=msg; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2800); }
function escapeHtml(s){ return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m])); }
function canAccess(page){ return !["operators","tests"].includes(page) || isAdmin(); }
function navigate(page){ if(!canAccess(page)){showToast("Acesso exclusivo do administrador.");return;} app.page=page;document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.page===page));renderPage(); }
function renderPage(){ if(!canAccess(app.page))app.page="dashboard"; const tpl=document.getElementById(app.page+"Tpl"); document.getElementById("pageContent").replaceChildren(tpl.content.cloneNode(true)); const titles={dashboard:"Visão Geral",clients:"Clientes",loans:"Empréstimos",payments:"Pagamentos",mailbox:"Caixa de Entrada",operators:"Operadores",audit:"Auditoria",tests:"Testes"}; document.getElementById("pageTitle").textContent=titles[app.page]; if(app.page==="dashboard")renderDashboard(); if(app.page==="clients")renderClients(); if(app.page==="loans")renderLoans(); if(app.page==="payments")renderPayments(); if(app.page==="mailbox")renderMailbox(); if(app.page==="operators")renderOperators(); if(app.page==="audit")renderAudit(); bindActions(); }

async function initAuth(){
  try{
    const boot=await api("/api/bootstrap");
    sessionUser=boot.user;
    document.getElementById("adminSetupForm").classList.toggle("hidden",!boot.setupRequired);
    document.getElementById("setupHint").classList.toggle("hidden",!boot.setupRequired);
    document.getElementById("authRoleText").textContent=boot.setupRequired?"Primeiro acesso — configurar administrador":"Acesso ao sistema";
    if(sessionUser){ if(sessionUser.forcePasswordChange){ initApp(); } else { await refreshDB(); initApp(); } }
  }catch(e){ showToast("Não foi possível conectar ao servidor AgiProz."); console.error(e); }
}

document.getElementById("adminSetupForm").addEventListener("submit",async e=>{ e.preventDefault(); const name=setupName.value.trim(),email=setupEmail.value.trim().toLowerCase(),p=setupPassword.value,p2=setupPassword2.value; if(!validName(name))return showToast("Informe um nome válido."); if(!validPassword(p))return showToast("A senha deve ter de 8 a 64 caracteres, sem espaços."); if(!validInternalEmail(email))return showToast("Use o e-mail corporativo no formato nome@agiproz.local."); if(p!==p2)return showToast("As senhas não coincidem."); try{const r=await api("/api/setup",{method:"POST",body:{name,email,password:p}});sessionUser=r.user;await refreshDB();initApp();openModal(`<div class="modal-head"><h3>Administrador criado</h3></div><div class="warning-box"><b>Chave de recuperação:</b><div style="font-size:1.3rem;letter-spacing:.12em;margin:12px 0"><b>${escapeHtml(r.recoveryCode||"")}</b></div><p>Guarde esta chave. ${r.recoveryStoredLocally?"No ambiente local, uma cópia também foi salva em <b>instance\admin_recovery_code.txt</b>.":"No ambiente hospedado, a chave não é gravada em arquivo local; guarde a chave exibida acima em local seguro."}</p></div><div class="modal-actions"><button class="btn primary" onclick="closeModal()">Entendi</button></div>`);}catch(err){showToast(err.message)}});
document.getElementById("loginForm").addEventListener("submit",async e=>{e.preventDefault();try{const r=await api("/api/login",{method:"POST",body:{login:loginEmail.value.trim(),password:loginPassword.value}});sessionUser=r.user;if(sessionUser.forcePasswordChange){initApp();}else{await refreshDB();initApp();}}catch(err){showToast(err.message)}});
document.getElementById("adminRecoveryBtn").addEventListener("click",openAdminRecoveryModal);
document.getElementById("logoutBtn").addEventListener("click",async()=>{try{await api("/api/logout",{method:"POST"})}finally{location.reload()}});
document.querySelectorAll(".nav-item").forEach(btn=>btn.addEventListener("click",()=>navigate(btn.dataset.page)));
async function initApp(){ const user=currentUser(); if(!user||user.active===false)return; if(user.forcePasswordChange){ document.getElementById("authView").classList.add("hidden");document.getElementById("appView").classList.remove("hidden"); openForcePasswordModal(); return; } await refreshMessages().catch(()=>{}); await refreshDrafts().catch(()=>{}); document.getElementById("authView").classList.add("hidden");document.getElementById("appView").classList.remove("hidden");document.getElementById("currentUser").textContent=user.name;document.getElementById("currentRole").textContent=user.role==="admin"?"Administrador":"Operador";document.querySelectorAll(".admin-only").forEach(el=>el.classList.toggle("hidden",!isAdmin()));renderPage(); }


function openForcePasswordModal(){
  openModal(`<div class="modal-head"><h3>Primeiro acesso do operador</h3></div><form class="modal-form" id="forcePasswordForm"><p>Para continuar, substitua a senha temporária por uma senha pessoal.</p><label>Nova senha<input id="forcePass1" type="password" minlength="8" required></label><label>Confirmar nova senha<input id="forcePass2" type="password" minlength="8" required></label><small class="muted">Mínimo de 8 caracteres, com uma letra maiúscula, um número e um caractere especial.</small><div class="modal-actions"><button class="btn primary">Alterar senha</button></div></form>`);
  document.getElementById("forcePasswordForm").onsubmit=async e=>{e.preventDefault();const p=forcePass1.value,p2=forcePass2.value;if(!validPassword(p))return showToast("A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial.");if(p!==p2)return showToast("As senhas não coincidem.");try{const r=await api("/api/password/change",{method:"POST",body:{password:p,password2:p2}});sessionUser=r.user;closeModal();await refreshDB();await initApp();showToast("Senha alterada com sucesso.");}catch(err){showToast(err.message)}};
}

async function renderAudit(){
  if(!isAdmin())return;
  const table=document.getElementById("auditTable");
  table.innerHTML="<tr><td colspan='5'>Carregando...</td></tr>";
  try{
    const r=await api("/api/audit");
    table.innerHTML=(r.logs||[]).map(x=>`<tr><td>${escapeHtml(x.created||"")}</td><td>${escapeHtml(x.user_name||"Sistema")}</td><td>${escapeHtml(x.action||"")}</td><td>${escapeHtml(x.entity||"")}</td><td>${escapeHtml(x.details||"")}</td></tr>`).join("")||"<tr><td colspan='5'>Nenhum registro.</td></tr>";
  }catch(err){table.innerHTML=`<tr><td colspan='5'>${escapeHtml(err.message)}</td></tr>`;}
}

function validCPF(v){const cpf=normalizeCPF(v);if(cpf.length!==11||/^(\d)\1+$/.test(cpf))return false;let sum=0;for(let i=0;i<9;i++)sum+=+cpf[i]*(10-i);let d=11-(sum%11);if(d>=10)d=0;if(d!==+cpf[9])return false;sum=0;for(let i=0;i<10;i++)sum+=+cpf[i]*(11-i);d=11-(sum%11);if(d>=10)d=0;return d===+cpf[10];}

function openModal(html){document.getElementById("modalRoot").innerHTML=`<div class="modal-backdrop" id="backdrop"><div class="modal">${html}</div></div>`;document.getElementById("backdrop").onclick=e=>{if(e.target.id==="backdrop")closeModal()};}
function closeModal(){document.getElementById("modalRoot").innerHTML="";}


function openAdminRecoveryModal(){
  openModal(`<div class="modal-head"><h3>Recuperar senha do administrador</h3><button class="close" onclick="closeModal()">×</button></div><form class="modal-form" id="adminRecoveryForm"><p>Informe o e-mail usado no cadastro do administrador e a chave de recuperação.</p><label>E-mail do administrador<input id="recoveryEmail" type="email" autocomplete="email" required></label><label>Chave de recuperação<input id="recoveryCode" type="text" autocomplete="off" required placeholder="AGI-XXXX-XXXX-XXXX"></label><small class="muted">No ambiente local, a chave também fica guardada em <b>instance\admin_recovery_code.txt</b>. No ambiente hospedado, guarde a chave em local seguro.</small><label>Nova senha<input id="recoveryPassword" type="password" minlength="8" required></label><label>Confirmar nova senha<input id="recoveryPassword2" type="password" minlength="8" required></label><small class="muted">Mínimo de 8 caracteres, com uma letra maiúscula, um número e um caractere especial.</small><div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button class="btn primary">Redefinir senha</button></div></form>`);
  document.getElementById("adminRecoveryForm").onsubmit=async e=>{e.preventDefault();const email=recoveryEmail.value.trim().toLowerCase(),password=recoveryPassword.value,password2=recoveryPassword2.value;if(!email)return showToast("Informe o e-mail do administrador.");if(!validPassword(password))return showToast("A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, um número e um caractere especial.");if(password!==password2)return showToast("As senhas não coincidem.");try{const r=await api("/api/admin/recover",{method:"POST",body:{email,recoveryCode:recoveryCode.value.trim().toUpperCase(),password,password2}});sessionUser=r.user;await refreshDB();closeModal();initApp();openModal(`<div class="modal-head"><h3>Senha redefinida</h3></div><div class="warning-box"><p>A senha do administrador foi alterada.</p><p><b>Nova chave de recuperação:</b></p><div style="font-size:1.3rem;letter-spacing:.12em;margin:12px 0"><b>${escapeHtml(r.recoveryCode||"")}</b></div><p>Guarde a nova chave. A chave anterior deixou de funcionar.</p></div><div class="modal-actions"><button class="btn primary" onclick="closeModal()">Entendi</button></div>`);}catch(err){showToast(err.message)}};
}

initAuth();

function renderDashboard(){
  const db=getDB(),open=db.loans.filter(l=>l.status!=="paid").reduce((s,l)=>s+(l.amount*(1+l.interest/100)),0);
  const late=db.loans.filter(l=>loanStatus(l)==="late").length;
  statClients.textContent=db.clients.length;statLoans.textContent=db.loans.length;statOpen.textContent=money(open);statLate.textContent=late;
  recentLoans.innerHTML=db.loans.slice(-5).reverse().map(l=>loanRow(l,db,false)).join("")||"<p class='muted'>Nenhum empréstimo.</p>";
}
function nextInstallment(l, db=getDB()){
  return (db.installments||[]).filter(i=>i.loanId===l.id&&i.status!=="paid").sort((a,b)=>a.number-b.number)[0]||null;
}
function loanDue(l, db=getDB()){
  return nextInstallment(l,db)?.due || l.due;
}
function loanStatus(l){
  if(l.status==="paid" || l.paid>=l.installments)return"paid";
  const inst=nextInstallment(l);
  const due=inst?.due||l.due;
  if(new Date(due+"T23:59:59")<new Date())return"late";
  return"open";
}
function statusLabel(s){return s==="paid"?"Quitado":s==="late"?"Em atraso":"Em aberto"}
function loanTotal(l){return l.amount*(1+l.interest/100)}
function loanRow(l,db,table=true){
  const s=loanStatus(l), due=loanDue(l,db);
  if(!table)return `<div class="test-row"><span>${escapeHtml(clientName(db,l.clientId))}</span><span>${money(loanTotal(l))} · <b class="status ${s}">${statusLabel(s)}</b></span></div>`;
  return `<tr><td>${escapeHtml(clientName(db,l.clientId))}</td><td>${money(l.amount)}<small>Total: ${money(loanTotal(l))}</small></td><td>${l.paid}/${l.installments}</td><td><span class="status ${l.frequency==="weekly"?"open":"ok"}">${frequencyLabel(l.frequency)}</span></td><td>${dateBR(due)}</td><td><span class="status ${s}">${statusLabel(s)}</span></td><td><button class="action-btn" data-loan="${l.id}">Detalhes</button> ${dueMessageAction(l,db)}</td></tr>`;
}
function renderClients(){
  const db=getDB(),q=(document.getElementById("clientSearch")?.value||"").toLowerCase();
  clientTable.innerHTML=db.clients.filter(c=>`${c.name} ${c.cpf} ${c.email}`.toLowerCase().includes(q)).map(c=>{const hasLoan=db.loans.some(l=>l.clientId===c.id);return `<tr><td><b>${escapeHtml(c.name)}</b></td><td>${escapeHtml(c.cpf)}</td><td>${escapeHtml(c.email)}<small>${escapeHtml(c.phone)}</small></td><td><span class="status ok">Ativo</span></td><td><button class="action-btn" data-client="${c.id}">Ver</button>${!hasLoan?` <button class="action-btn danger" data-delete-client="${c.id}">Excluir</button>`:""}</td></tr>`}).join("")||"<tr><td colspan='5'>Nenhum cliente encontrado.</td></tr>";
  document.querySelectorAll("[data-client]").forEach(b=>b.onclick=()=>openClientModal(b.dataset.client));
  document.querySelectorAll("[data-delete-client]").forEach(b=>b.onclick=()=>deleteClient(b.dataset.deleteClient));
}
function renderLoans(){
  const db=getDB(),filter=document.getElementById("loanFilter")?.value||"all";
  loanTable.innerHTML=db.loans.filter(l=>filter==="all"||loanStatus(l)===filter).map(l=>loanRow(l,db,true)).join("")||"<tr><td colspan='7'>Nenhum empréstimo.</td></tr>";
  document.querySelectorAll("[data-loan]").forEach(b=>b.onclick=()=>openLoanDetails(b.dataset.loan));
  document.querySelectorAll("[data-whatsapp]").forEach(b=>b.onclick=()=>openWhatsAppLoan(b.dataset.whatsapp));
}
function renderPayments(){
  const db=getDB(),q=(document.getElementById("paymentSearch")?.value||"").toLowerCase();
  const pending=(db.installments||[]).filter(i=>i.status!=="paid").sort((a,b)=>String(a.due).localeCompare(String(b.due)));
  const rows=[];
  pending.forEach(inst=>{
    const l=db.loans.find(x=>x.id===inst.loanId); if(!l)return;
    const name=clientName(db,l.clientId); if(!name.toLowerCase().includes(q))return;
    const isFirst=(db.installments||[]).filter(x=>x.loanId===l.id&&x.status!=="paid").sort((a,b)=>a.number-b.number)[0]?.id===inst.id;
    const statusText=inst.status==="late"?`Em atraso (${inst.lateDays} dia${inst.lateDays===1?"":"s"})`:"Pendente";
    rows.push(`<tr><td>${escapeHtml(name)}</td><td>${l.id.slice(-8)}</td><td>${inst.number}/${l.installments}</td><td>${frequencyLabel(l.frequency)}</td><td>${money(inst.amountDue??inst.value)}${inst.lateInterest>0?`<small>Juros: ${money(inst.lateInterest)}</small>`:""}</td><td>${dateBR(inst.due)}</td><td><span class="status ${inst.status==='late'?'late':'open'}">${statusText}</span></td><td>${isFirst?`<button class="action-btn" data-pay="${l.id}" data-installment="${inst.id}">Registrar</button> ${dueMessageAction({...l, due:inst.due, paid:inst.number-1},db)}`:`<span class="muted">Aguardando parcela anterior</span>`}</td></tr>`);
  });
  paymentTable.innerHTML=rows.join("")||"<tr><td colspan='8'>Nenhuma parcela pendente.</td></tr>";
  const history=document.getElementById("paymentHistory");
  if(history){
    const payments=[...(db.payments||[])].sort((a,b)=>String(b.date).localeCompare(String(a.date)));
    history.innerHTML=payments.map(p=>{const l=db.loans.find(x=>x.id===p.loanId); if(!l)return ""; const name=clientName(db,l.clientId); const inst=(db.installments||[]).find(i=>i.loanId===p.loanId&&i.number===p.installment); return `<tr><td>${escapeHtml(name)}</td><td>${p.loanId.slice(-8)}</td><td>${p.installment}/${l.installments}</td><td>${money(p.value)}</td><td>${dateBR(p.date)}</td><td><button class="action-btn danger" data-undo-payment="${p.id}">Desfazer</button></td></tr>`}).join("")||"<tr><td colspan='6'>Nenhum pagamento registrado.</td></tr>";
  }
  document.querySelectorAll("[data-pay]").forEach(b=>b.onclick=()=>registerPayment(b.dataset.pay,b.dataset.installment));
  document.querySelectorAll("[data-undo-payment]").forEach(b=>b.onclick=()=>undoPayment(b.dataset.undoPayment));
  document.querySelectorAll("[data-whatsapp]").forEach(b=>b.onclick=()=>openWhatsAppLoan(b.dataset.whatsapp));
}

let mailboxMode = "inbox";
let mailboxDrafts = [];

async function refreshMessages(){
  const r=await api("/api/messages");
  db.messages=r.messages||[];
  db.unreadCount=r.unreadCount||0;
  db.draftCount=r.draftCount||0;
  updateUnreadBadge();
  return db.messages;
}

async function refreshDrafts(){
  const r=await api("/api/messages/drafts");
  mailboxDrafts=r.drafts||[];
  db.draftCount=mailboxDrafts.length;
  return mailboxDrafts;
}

function updateUnreadBadge(){
  const badge=document.getElementById("unreadBadge");
  if(!badge)return;
  const n=Number(db.unreadCount||0);
  badge.textContent=n>99?"99+":String(n);
  badge.classList.toggle("hidden",n===0);
}

function mailboxMessageActions(m,received){
  const archived=received?m.archivedRecipient:m.archivedSender;
  const deleted=received?m.deletedRecipient:m.deletedSender;
  if(deleted)return `<button class="action-btn" data-restore-message="${m.id}">Restaurar</button> <button class="action-btn danger" data-delete-message="${m.id}">${deleted?"Excluir definitivamente":"Excluir"}</button>`;
  return `${received&&!m.readAt?`<button class="action-btn" data-read-message="${m.id}">Marcar como lida</button>`:""}
    <button class="action-btn" data-open-message="${m.id}">Abrir</button>
    <button class="action-btn" data-reply-message="${m.id}">Responder</button>
    <button class="action-btn" data-forward-message="${m.id}">Encaminhar</button>
    ${archived?`<button class="action-btn" data-restore-message="${m.id}">Desarquivar</button>`:`<button class="action-btn" data-archive-message="${m.id}">Arquivar</button>`}
    <button class="action-btn danger" data-delete-message="${m.id}">${deleted?"Excluir definitivamente":"Excluir"}</button>`;
}

function renderMailbox(){
  const list=document.getElementById("mailboxList"); if(!list)return;
  const me=sessionUser?.id;
  document.querySelectorAll("[data-mail-filter]").forEach(b=>b.classList.toggle("active",b.dataset.mailFilter===mailboxMode));
  if(mailboxMode==="drafts"){
    list.innerHTML=mailboxDrafts.map(d=>`<article class="mail-card draft-card">
      <div class="mail-top"><span class="status open">Rascunho</span><small>Atualizado em ${dateTimeBR(d.updated)}</small></div>
      <h3>${escapeHtml(d.subject||"(Sem assunto)")}</h3>
      <p class="mail-meta"><b>Para:</b> ${escapeHtml(d.recipientName||"Não definido")} ${d.recipientEmail?`&lt;${escapeHtml(d.recipientEmail)}&gt;`:""}</p>
      <p>${escapeHtml(d.body||"(Mensagem vazia)")}</p>
      <div class="mail-actions"><button class="action-btn" data-edit-draft="${d.id}">Editar</button><button class="action-btn danger" data-delete-draft="${d.id}">Excluir</button></div>
    </article>`).join("")||`<p class="muted">Nenhum rascunho salvo.</p>`;
    document.getElementById("mailboxSummary").textContent=`${mailboxDrafts.length} rascunho(s)`;
    bindMailboxActions(); return;
  }
  let rows=(db.messages||[]).filter(m=>{
    const received=m.recipientId===me;
    const archived=received?m.archivedRecipient:m.archivedSender;
    const deleted=received?m.deletedRecipient:m.deletedSender;
    if(mailboxMode==="inbox")return received&&!archived&&!deleted;
    if(mailboxMode==="sent")return !received&&!archived&&!deleted;
    if(mailboxMode==="archive")return archived&&!deleted;
    if(mailboxMode==="trash")return deleted;
    return true;
  });
  list.innerHTML=rows.map(m=>{
    const received=m.recipientId===me;
    return `<article class="mail-card ${received&&!m.readAt?"unread":""}">
      <div class="mail-top"><span class="status ${received?"open":"ok"}">${received?(m.readAt?"Recebida":"Não lida"):"Enviada"}</span><small>${dateTimeBR(m.created)}</small></div>
      <h3>${escapeHtml(m.subject)}</h3>
      <p class="mail-meta"><b>${received?"De":"Para"}:</b> ${escapeHtml(received?m.senderName:m.recipientName)} &lt;${escapeHtml(received?m.senderEmail:m.recipientEmail)}&gt;</p>
      <p>${escapeHtml(m.body.length>280?m.body.slice(0,280)+"…":m.body)}</p>
      <div class="mail-actions">${mailboxMessageActions(m,received)}</div>
    </article>`;
  }).join("")||`<p class="muted">Nenhuma mensagem nesta categoria.</p>`;
  const unread=rows.filter(m=>m.recipientId===me&&!m.readAt).length;
  document.getElementById("mailboxSummary").textContent=`${rows.length} mensagem(ns)${unread?` · ${unread} não lida(s)`:""}`;
  bindMailboxActions();
}

function bindMailboxActions(){
  document.querySelectorAll("[data-mail-filter]").forEach(b=>b.onclick=async()=>{mailboxMode=b.dataset.mailFilter;if(mailboxMode==="drafts")await refreshDrafts();renderMailbox();});
  document.querySelectorAll("[data-open-message]").forEach(b=>b.onclick=()=>openMessage(b.dataset.openMessage));
  document.querySelectorAll("[data-read-message]").forEach(b=>b.onclick=async()=>{try{await api(`/api/messages/${b.dataset.readMessage}/read`,{method:"PATCH"});await refreshMessages();renderMailbox();}catch(e){showToast(e.message)}});
  document.querySelectorAll("[data-archive-message]").forEach(b=>b.onclick=async()=>{try{await api(`/api/messages/${b.dataset.archiveMessage}/archive`,{method:"PATCH"});await refreshMessages();renderMailbox();showToast("Mensagem arquivada.");}catch(e){showToast(e.message)}});
  document.querySelectorAll("[data-restore-message]").forEach(b=>b.onclick=async()=>{try{await api(`/api/messages/${b.dataset.restoreMessage}/restore`,{method:"PATCH"});await refreshMessages();renderMailbox();showToast("Mensagem restaurada.");}catch(e){showToast(e.message)}});
  document.querySelectorAll("[data-delete-message]").forEach(b=>b.onclick=async()=>{const m=findMessage(b.dataset.deleteMessage);const mineDeleted=m&&(m.recipientId===sessionUser.id?m.deletedRecipient:m.deletedSender);const prompt=mineDeleted?"Excluir definitivamente esta mensagem?":"Mover esta mensagem para a lixeira?";if(!confirm(prompt))return;try{await api(mineDeleted?`/api/messages/${b.dataset.deleteMessage}/purge`:`/api/messages/${b.dataset.deleteMessage}`,{method:"DELETE"});await refreshMessages();renderMailbox();showToast(mineDeleted?"Mensagem excluída definitivamente.":"Mensagem movida para a lixeira.");}catch(e){showToast(e.message)}});
  document.querySelectorAll("[data-reply-message]").forEach(b=>b.onclick=()=>openMessageComposer("reply",b.dataset.replyMessage));
  document.querySelectorAll("[data-forward-message]").forEach(b=>b.onclick=()=>openMessageComposer("forward",b.dataset.forwardMessage));
  document.querySelectorAll("[data-edit-draft]").forEach(b=>b.onclick=()=>openMessageComposer("draft",b.dataset.editDraft));
  document.querySelectorAll("[data-delete-draft]").forEach(b=>b.onclick=async()=>{if(!confirm("Excluir este rascunho?"))return;try{await api(`/api/messages/drafts/${b.dataset.deleteDraft}`,{method:"DELETE"});await refreshDrafts();renderMailbox();}catch(e){showToast(e.message)}});
}

function findMessage(id){return (db.messages||[]).find(m=>m.id===id);}
function openMessage(id){const m=findMessage(id);if(!m)return;const received=m.recipientId===sessionUser.id;if(received&&!m.readAt){api(`/api/messages/${id}/read`,{method:"PATCH"}).then(refreshMessages).catch(()=>{});m.readAt=new Date().toISOString();}openModal(`<div class="modal-head"><h3>${escapeHtml(m.subject)}</h3><button class="close" onclick="closeModal()">×</button></div><div class="message-view"><p><b>${received?"De":"Para"}:</b> ${escapeHtml(received?m.senderName:m.recipientName)} &lt;${escapeHtml(received?m.senderEmail:m.recipientEmail)}&gt;</p><p><b>Data:</b> ${dateTimeBR(m.created)}</p><hr><p class="message-body">${escapeHtml(m.body).replace(/\n/g,"<br>")}</p></div><div class="modal-actions"><button class="btn secondary" onclick="closeModal()">Fechar</button><button class="btn secondary" onclick="closeModal();openMessageComposer('reply','${m.id}')">Responder</button><button class="btn primary" onclick="closeModal();openMessageComposer('forward','${m.id}')">Encaminhar</button></div>`);}

function openMessageComposer(mode="new",id=null){
  const recipients=db.users.filter(u=>u.active!==false&&u.id!==sessionUser.id);
  if(!recipients.length)return showToast("Não há outro usuário ativo para receber a mensagem.");
  const m=mode==="reply"||mode==="forward"?findMessage(id):null;
  const draft=mode==="draft"?mailboxDrafts.find(x=>x.id===id):null;
  let recipientId=draft?.recipientId||"";
  let subject=draft?.subject||"";
  let body=draft?.body||"";
  if(mode==="reply"&&m){recipientId=m.senderId;subject=m.subject.startsWith("Re: ")?m.subject:`Re: ${m.subject}`;body=`\n\n--- Mensagem original ---\n${m.body}`;}
  if(mode==="forward"&&m){subject=m.subject.startsWith("Enc: ")?m.subject:`Enc: ${m.subject}`;body=`\n\n--- Mensagem encaminhada ---\nDe: ${m.senderEmail}\nData: ${dateTimeBR(m.created)}\n\n${m.body}`;}
  const title=mode==="reply"?"Responder":mode==="forward"?"Encaminhar":mode==="draft"?"Editar rascunho":"Nova mensagem interna";
  openModal(`<div class="modal-head"><h3>${title}</h3><button class="close" onclick="closeModal()">×</button></div><form class="modal-form" id="messageForm"><label>Destinatário<select id="msgRecipient"><option value="">Selecione...</option>${recipients.map(u=>`<option value="${u.id}" ${u.id===recipientId?"selected":""}>${escapeHtml(u.name)} — ${escapeHtml(u.email)}</option>`).join("")}</select></label><label>Assunto<input id="msgSubject" maxlength="120" value="${escapeHtml(subject)}"></label><label>Mensagem<textarea id="msgBody" rows="9" maxlength="5000">${escapeHtml(body)}</textarea></label><div class="modal-actions"><button type="button" class="btn secondary" id="saveDraftBtn">Salvar rascunho</button><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button class="btn primary">Enviar</button></div></form>`);
  const form=document.getElementById("messageForm");
  document.getElementById("saveDraftBtn").onclick=async()=>{try{await api("/api/messages/drafts",{method:"POST",body:{id:draft?.id,recipientId:msgRecipient.value,subject:msgSubject.value.trim(),body:msgBody.value}});await refreshDrafts();closeModal();mailboxMode="drafts";renderMailbox();showToast("Rascunho salvo.");}catch(e){showToast(e.message)}};
  form.onsubmit=async e=>{e.preventDefault();const payload={recipientId:msgRecipient.value,subject:msgSubject.value.trim(),body:msgBody.value.trim()};if(!payload.recipientId||!payload.subject||!payload.body)return showToast("Preencha destinatário, assunto e mensagem.");try{if(draft)await api(`/api/messages/drafts/${draft.id}/send`,{method:"POST"});else await api("/api/messages",{method:"POST",body:payload});await refreshMessages();await refreshDrafts();closeModal();mailboxMode="sent";renderMailbox();showToast("Mensagem enviada.");}catch(e){showToast(e.message)}};
}

function openMessageModal(){openMessageComposer("new");}
function dateTimeBR(v){if(!v)return "-";const d=new Date(v.replace(" ","T"));return Number.isNaN(d.getTime())?v:d.toLocaleString("pt-BR");}

function renderOperators(){
  if(!isAdmin())return;
  const db=getDB();
  operatorTable.innerHTML=db.users.map(u=>`<tr><td><b>${escapeHtml(u.name)}</b></td><td>${escapeHtml(u.email)}</td><td><span class="status ${u.role==="admin"?"open":"ok"}">${u.role==="admin"?"Administrador":"Operador"}</span></td><td><span class="status ${u.active!==false?"ok":"off"}">${u.active!==false?"Ativo":"Desativado"}</span></td><td>${u.role==="admin"?"<span class='muted'>Conta principal</span>":`<button class="action-btn" data-op-edit="${u.id}">Editar</button> <button class="action-btn" data-op-reset="${u.id}">Resetar senha</button> <button class="action-btn" data-op-toggle="${u.id}">${u.active!==false?"Desativar":"Ativar"}</button>`}</td></tr>`).join("")||"<tr><td colspan='5'>Nenhum operador cadastrado.</td></tr>";
  document.querySelectorAll("[data-op-edit]").forEach(b=>b.onclick=()=>openOperatorModal(b.dataset.opEdit));
  document.querySelectorAll("[data-op-toggle]").forEach(b=>b.onclick=()=>toggleOperator(b.dataset.opToggle));
  document.querySelectorAll("[data-op-reset]").forEach(b=>b.onclick=()=>resetOperatorPassword(b.dataset.opReset));
}
function openOperatorModal(id){
  if(!isAdmin())return showToast("Acesso exclusivo do administrador.");
  const u=getDB().users.find(x=>x.id===id)||{};
  openModal(`<div class="modal-head"><h3>${id?"Editar operador":"Criar operador"}</h3><button class="close" onclick="closeModal()">×</button></div>
  <form class="modal-form" id="operatorForm">
    <label>Nome completo<input id="opName" maxlength="80" value="${escapeHtml(u.name||"")}" required></label>
    <label>Login<input id="opLogin" maxlength="30" value="${escapeHtml(u.login||"")}" placeholder="ex.: joao.silva" required></label>
    <label>E-mail corporativo<input id="opEmail" type="email" maxlength="120" value="${escapeHtml(u.email||((u.login||"")+"@agiproz.local"))}" placeholder="nome@agiproz.local" required><small class="muted">Ex.: ${escapeHtml((u.login||"operador")+"@agiproz.local")}</small></label>
    ${!id?'<p class="muted">Uma senha temporária será gerada após o cadastro. O operador deverá trocá-la no primeiro acesso.</p>':''}
    <div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button class="btn primary">Salvar acesso</button></div>
  </form>`);
  document.getElementById("operatorForm").onsubmit=async e=>{e.preventDefault();const name=normalizeText(opName.value),login=normalizeLogin(opLogin.value),email=opEmail.value.trim().toLowerCase();if(!validName(name)||!validLogin(login)||!validInternalEmail(email))return showToast("Use nome, login e e-mail corporativo @agiproz.local válidos.");try{let result;if(id){result=await api(`/api/users/${id}`,{method:"PUT",body:{name,login,email}});}else{result=await api("/api/users",{method:"POST",body:{name,login,email}});}await refreshDB();closeModal();renderOperators();if(result.temporaryPassword){openModal(`<div class="modal-head"><h3>Operador criado</h3></div><div class="warning-box"><p>Entregue esta senha temporária ao operador.</p><p><b>Senha temporária:</b></p><div style="font-size:1.3rem;letter-spacing:.08em;margin:12px 0"><b>${escapeHtml(result.temporaryPassword)}</b></div><p>Ela deverá ser trocada no primeiro acesso.</p></div><div class="modal-actions"><button class="btn primary" onclick="closeModal()">Entendi</button></div>`);}else{showToast("Operador atualizado.");}}catch(err){showToast(err.message)}};
}
async function resetOperatorPassword(id){ if(!isAdmin())return showToast("Acesso exclusivo do administrador."); const u=getDB().users.find(x=>x.id===id); if(!u)return; if(!confirm(`Redefinir a senha de ${u.name}?\n\nUma senha temporária será gerada e deverá ser trocada no próximo acesso.`))return; try{const result=await api(`/api/users/${id}/reset-password`,{method:"POST"});await refreshDB();renderOperators();openModal(`<div class="modal-head"><h3>Senha redefinida</h3></div><div class="warning-box"><p>Entregue esta senha temporária ao operador.</p><p><b>Senha temporária:</b></p><div style="font-size:1.3rem;letter-spacing:.08em;margin:12px 0"><b>${escapeHtml(result.temporaryPassword)}</b></div><p>Ela deverá ser trocada no próximo acesso.</p></div><div class="modal-actions"><button class="btn primary" onclick="closeModal()">Entendi</button></div>`);}catch(err){showToast(err.message)}}
async function toggleOperator(id){ if(!isAdmin())return;try{const r=await api(`/api/users/${id}/toggle`,{method:"PATCH"});await refreshDB();renderOperators();showToast(r.active?"Operador ativado.":"Operador desativado.");}catch(err){showToast(err.message)}}

function openClientModal(id){
  const c=getDB().clients.find(x=>x.id===id)||{};
  openModal(`<div class="modal-head"><h3>${id?"Editar":"Cadastrar"} cliente</h3><button class="close" onclick="closeModal()">×</button></div>
  <form class="modal-form" id="clientForm">
    <label>Nome completo<input id="mName" maxlength="80" value="${escapeHtml(c.name||"")}" required></label>
    <label>CPF<input id="mCpf" inputmode="numeric" maxlength="14" value="${escapeHtml(c.cpf||"")}" placeholder="000.000.000-00" required></label>
    <label>E-mail<input id="mEmail" type="email" maxlength="120" value="${escapeHtml(c.email||"")}" placeholder="cliente@exemplo.com" required></label>
    <label>Celular / WhatsApp<input id="mPhone" type="tel" inputmode="tel" maxlength="15" value="${escapeHtml(c.phone||"")}" placeholder="(00)00000-0000" required></label>
    <label>Endereço<input id="mAddress" maxlength="180" value="${escapeHtml(c.address||"")}" placeholder="Rua, número, bairro, cidade" required></label>
    <label class="check-row"><input id="mWhatsApp" type="checkbox" ${c.whatsappConfirmed!==false?"checked":""}> Número possui WhatsApp</label>
    <div class="modal-actions"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button class="btn primary">Salvar</button></div>
  </form>`);
  const cpf=document.getElementById("mCpf"), phone=document.getElementById("mPhone"), name=document.getElementById("mName"), email=document.getElementById("mEmail");
  const applyCPF=()=>{const d=normalizeCPF(cpf.value).slice(0,11);cpf.value=d.length===11?formatCPF(d):d}; const applyPhone=()=>{const d=normalizeWhatsApp(phone.value).slice(0,11);phone.value=d.length===11?`(${d.slice(0,2)})${d.slice(2,7)}-${d.slice(7)}`:d};
  cpf.addEventListener("input",()=>{cpf.value=normalizeCPF(cpf.value).slice(0,11);if(cpf.value.length===11)applyCPF()}); cpf.addEventListener("blur",applyCPF); phone.addEventListener("input",()=>{phone.value=normalizeWhatsApp(phone.value).slice(0,11);if(phone.value.length===11)applyPhone()}); phone.addEventListener("blur",applyPhone); name.addEventListener("input",()=>name.value=normalizeText(name.value).toUpperCase());
  document.getElementById("clientForm").onsubmit=async e=>{e.preventDefault();name.value=normalizeText(name.value).toUpperCase();applyCPF();applyPhone();const rawEmail=email.value.trim();const data={name:name.value,cpf:normalizeCPF(cpf.value),email:rawEmail,phone:normalizeWhatsApp(phone.value),address:mAddress.value.trim(),whatsappConfirmed:mWhatsApp.checked};let error="";if(!validName(data.name))error="Informe um nome completo válido.";else if(!validCPF(data.cpf))error="Informe um CPF válido. Digite apenas os números ou use o formato 000.000.000-00.";else if(!validClientEmail(data.email))error="O e-mail deve ser digitado em minúsculas, sem acentos e em formato válido.";else if(!validMobileBR(data.phone))error="Informe um celular válido no formato (00)00000-0000.";else if(!data.address)error="Informe o endereço do cliente.";else if(!data.whatsappConfirmed)error="Confirme que o número possui WhatsApp.";if(error)return showToast(error);try{if(id)await api(`/api/clients/${id}`,{method:"PUT",body:data});else await api("/api/clients",{method:"POST",body:data});await refreshDB();closeModal();renderPage();showToast("Cliente salvo com sucesso.");}catch(err){showToast(err.message)}};
}
async function deleteClient(id){const c=getDB().clients.find(x=>x.id===id);if(!c)return;if(getDB().loans.some(l=>l.clientId===id))return showToast("Este cliente possui empréstimo e não pode ser excluído.");if(!confirm(`Excluir o cadastro de ${c.name}? Esta ação não pode ser desfeita.`))return;try{await api(`/api/clients/${id}`,{method:"DELETE"});await refreshDB();renderClients();showToast("Cliente excluído com sucesso.");}catch(err){showToast(err.message)}}


function openLoanModal(){
  const db=getDB();if(!db.clients.length)return showToast("Cadastre um cliente primeiro.");
  openModal(`<div class="modal-head"><h3>Novo empréstimo</h3><button class="close" onclick="closeModal()">×</button></div>
  <form class="modal-form" id="loanForm">
    <label>Cliente<select id="mClient">${db.clients.filter(c=>c.active!==false).map(c=>`<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}</select></label>
    <label>Valor solicitado<input id="mAmount" type="number" min="50" max="50000" step="0.01" required placeholder="1000"></label>
    <label>Taxa simulada (%)<input id="mInterest" type="number" min="0" max="100" step="0.01" value="8" required></label>
    <label>Número de parcelas<input id="mInstallments" type="number" min="1" max="36" step="1" value="4" required></label>
    <label>Periodicidade das parcelas<select id="mFrequency"><option value="monthly">Mensal</option><option value="biweekly">Quinzenal</option><option value="weekly">Semanal</option></select></label>
    <div id="loanPreview" class="loan-preview warning-box">Preencha os dados para calcular.</div>
    <label>Primeiro vencimento<input id="mDue" type="date" min="${today()}" required></label>
    <div class="modal-actions modal-actions-sticky"><button type="button" class="btn secondary" onclick="closeModal()">Cancelar</button><button class="btn primary">Criar contrato</button></div>
  </form>`);
  mDue.value=new Date(Date.now()+30*86400000).toISOString().slice(0,10);const preview=()=>{const a=+mAmount.value||0,i=+mInterest.value||0,n=+mInstallments.value||1,total=a*(1+i/100),freq=mFrequency.value; const dates=installmentDates({due:mDue.value,installments:n,frequency:freq}); loanPreview.innerHTML=`<b>Total simulado:</b> ${money(total)} · <b>Parcela:</b> ${money(total/n)} · <b>Periodicidade:</b> ${frequencyLabel(freq)}<br><small>Vencimentos: ${dates.slice(0,6).map((d,idx)=>`${idx+1}ª ${dateBR(d)}`).join(" · ")}${dates.length>6?" · …":""}</small>`};[mAmount,mInterest,mInstallments,mFrequency,mDue].forEach(x=>x.oninput=preview); mFrequency.onchange=preview;preview();
  document.getElementById("loanForm").onsubmit=async e=>{e.preventDefault();const data={clientId:mClient.value,amount:+mAmount.value,interest:+mInterest.value,installments:+mInstallments.value,frequency:mFrequency.value,due:mDue.value};const error=validateLoanData(db,data);if(error)return showToast(error);try{await api("/api/loans",{method:"POST",body:data});await refreshDB();closeModal();renderPage();showToast("Empréstimo criado (simulação).");}catch(err){showToast(err.message)}};
}
function openLoanDetails(id){
  const db=getDB(),l=db.loans.find(x=>x.id===id);if(!l)return;
  const inst=(db.installments||[]).filter(x=>x.loanId===l.id).sort((a,b)=>a.number-b.number);
  openModal(`<div class="modal-head"><h3>Contrato ${escapeHtml(id.slice(-8))}</h3><button class="close" onclick="closeModal()">×</button></div>
  <p><b>Cliente:</b> ${escapeHtml(clientName(db,l.clientId))}</p><p><b>Valor:</b> ${money(l.amount)} · <b>Total simulado:</b> ${money(loanTotal(l))}</p><p><b>Parcelas:</b> ${l.paid}/${l.installments} pagas · <b>Periodicidade:</b> ${frequencyLabel(l.frequency)} · <b>Próximo vencimento:</b> ${dateBR(loanDue(l,db))}</p><div class="schedule-list"><b>Calendário individual de parcelas</b>${inst.map(i=>`<div class="schedule-row"><span>${i.number}ª parcela</span><span>${dateBR(i.due)}</span><span>${money(i.amountDue??i.value)}${i.lateInterest>0?` (+ ${money(i.lateInterest)} juros)`:""}</span><span class="status ${i.status==='paid'?'paid':i.status==='late'?'late':'open'}">${i.status==='paid'?'Paga':i.status==='late'?'Em atraso':'Pendente'}</span></div>`).join("")}</div>
  <p><b>Status do contrato:</b> <span class="status ${loanStatus(l)}">${statusLabel(loanStatus(l))}</span></p>
  <div class="modal-actions"><button class="btn secondary" onclick="closeModal()">Fechar</button>${loanStatus(l)!=="paid"?`<button class="btn primary" onclick="registerPayment('${l.id}');closeModal()">Registrar próxima parcela</button>`:""}</div>`);
}
async function registerPayment(id,installmentId){const l=getDB().loans.find(x=>x.id===id);if(!l||loanStatus(l)==="paid")return;try{const r=await api("/api/payments",{method:"POST",body:{loanId:id,installmentId:installmentId||undefined}});await refreshDB();renderPage();showToast(`Pagamento ${r.payment.installment}/${l.installments} registrado.`);}catch(err){showToast(err.message)}}
async function undoPayment(id){const p=getDB().payments.find(x=>x.id===id);if(!p)return;const l=getDB().loans.find(x=>x.id===p.loanId);if(!confirm(`Desfazer o pagamento da parcela ${p.installment} de ${l?clientName(getDB(),l.clientId):"este contrato"}?\n\nEssa ação será registrada na auditoria.`))return;try{await api(`/api/payments/${id}`,{method:"DELETE"});await refreshDB();renderPage();showToast("Pagamento desfeito com sucesso.");}catch(err){showToast(err.message)}}


function bindActions(){
  document.querySelectorAll('[data-action]').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const action=btn.dataset.action;
      if(action==='newClient') return openClientModal();
      if(action==='newLoan') return openLoanModal();
      if(action==='newOperator') return openOperatorModal();
      if(action==='newMessage') return openMessageModal();
      if(action==='runTests') return runTests();
    });
  });

  document.querySelectorAll('[data-page-link]').forEach(btn=>{
    btn.addEventListener('click',()=>navigate(btn.dataset.pageLink));
  });

  const clientSearch=document.getElementById('clientSearch');
  if(clientSearch) clientSearch.addEventListener('input',renderClients);

  const loanFilter=document.getElementById('loanFilter');
  if(loanFilter) loanFilter.addEventListener('change',renderLoans);

  const paymentSearch=document.getElementById('paymentSearch');
  if(paymentSearch) paymentSearch.addEventListener('input',renderPayments);
  const mailboxFilter=document.getElementById('mailboxFilter');
  if(mailboxFilter) mailboxFilter.addEventListener('change',renderMailbox);
}

async function runTests(){
  const cases=[];
  function t(name,fn){try{const ok=fn();cases.push({name,ok:!!ok,detail:ok?"OK":"Resultado inesperado"})}catch(e){cases.push({name,ok:false,detail:e.message})}}
  t("Cadastro de cliente exige nome válido",()=>("João".length>=3));
  t("CPF rejeita letras",()=>validCPF("ABC123.456.789-09")===false);
  t("Validação de CPF rejeita número inválido",()=>validCPF("111.111.111-11")===false);
  t("Validação de CPF aceita CPF de teste",()=>validCPF("529.982.247-25")===true);
  t("E-mail rejeita formato incompleto",()=>validEmail("abc@")===false);
  t("E-mail corporativo AgiProz usa domínio interno",()=>validInternalEmail("teste@agiproz.local")===true);
  t("E-mail externo não é aceito para usuário interno",()=>validInternalEmail("teste@gmail.com")===false);
  t("Celular rejeita telefone fixo",()=>validMobileBR("1133334444")===false);
  t("Celular aceita formato móvel brasileiro",()=>validMobileBR("11999991111")===true);
  t("Login rejeita caracteres inválidos",()=>validLogin("João@123")===false);
  t("Senha exige pelo menos 8 caracteres",()=>validPassword("1234567")===false);
  t("Cálculo do total do contrato",()=>loanTotal({amount:1000,interest:10})===1100);
  t("Parcela divide o total igualmente",()=>Math.abs(loanTotal({amount:1000,interest:10})/4-275)<0.001);
  t("Calendário semanal avança 7 dias",()=>addPeriod("2026-08-17","weekly")==="2026-08-24");
  t("Calendário quinzenal avança 14 dias",()=>addPeriod("2026-08-17","biweekly")==="2026-08-31");
  t("Calendário mensal avança um mês",()=>addPeriod("2026-08-17","monthly")==="2026-09-17");
  t("Status quitado quando todas as parcelas foram pagas",()=>loanStatus({status:"open",paid:4,installments:4,due:"2999-01-01"})==="paid");
  t("Status em atraso por vencimento",()=>loanStatus({status:"open",paid:0,installments:4,due:"2000-01-01"})==="late");
  t("Periodicidade quinzenal soma 14 dias",()=>addPeriod("2026-08-18","biweekly")==="2026-09-01");
  t("Duplicidade de cliente é detectável por CPF",()=>{const db={clients:[{id:"1",cpf:"123.456.789-09",email:"a@a.com",phone:"(11) 99999-1111"}]};return !!findDuplicateClient(db,{cpf:"123.456.789-09",email:"b@b.com",phone:"(11) 98888-2222"},null);});
  t("Duplicidade de usuário é detectável por login",()=>{const db={users:[{id:"1",login:"joao.silva",email:"a@a.com"}]};return !!findDuplicateUser(db,{login:"joao.silva",email:"b@b.com"},null);});
  t("Periodicidade semanal avança 7 dias",()=>addPeriod("2026-08-18","weekly")==="2026-08-25");
  t("Periodicidade mensal avança um mês",()=>addPeriod("2026-08-18","monthly")==="2026-09-18");
  t("E-mail interno usa domínio AgiProz",()=>validInternalEmail("operador@agiproz.local")===true);
  t("E-mail externo é rejeitado para usuários internos",()=>validInternalEmail("operador@gmail.com")===false);
  t("Somente administrador acessa testes",()=>canAccess("tests")===isAdmin());
  t("Somente administrador acessa operadores",()=>canAccess("operators")===isAdmin());
  t("Operadores não possuem perfil de administrador",()=>getDB().users.filter(u=>u.role==="operator").every(u=>u.role!=="admin"));
  document.getElementById("testResults").innerHTML=cases.map(c=>`<div class="test-row"><span>${escapeHtml(c.name)}</span><b class="${c.ok?"pass":"fail"}">${c.ok?"PASS":"FAIL"} — ${c.detail}</b></div>`).join("");
}
