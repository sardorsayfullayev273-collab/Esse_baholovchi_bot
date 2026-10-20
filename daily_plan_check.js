// Kunlik 5 savol jadvali: har kuni 5 ta takrorlanmaydigan savol, hamma uchun bir xil, 10 mavzuning hammasi qamrab olinadi.
// Ishga tushirish: cd miniapp && node ../tests/daily_plan_check.js
const fs=require('fs'),vm=require('vm');
const src=fs.readFileSync('games.js','utf8');
const ctx={console,setTimeout,clearInterval,setInterval,Math,Date,JSON,Promise,Set,Object,Array,String,Number,
  localStorage:{getItem:()=>null,setItem(){}},document:{getElementById:()=>null,addEventListener(){},querySelector:()=>null},navigator:{},
  fetch:()=>{throw new Error('no net')}};
ctx.window=Object.assign(ctx,{addEventListener(){},removeEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})}); vm.createContext(ctx);
try{vm.runInContext(src,ctx)}catch(e){console.log('yuklash xatosi',e.message);process.exit(1)}
vm.runInContext(`
gmGet = async (f)=>JSON.parse(require_fs.readFileSync(f.split('?')[0],'utf8'));
gmLoadBlocked = async()=>{}; 
`,Object.assign(ctx,{require_fs:fs}));
(async()=>{
  const b=JSON.parse(fs.readFileSync('dtm_bank.json','utf8'));
  vm.runInContext('GMD.bank=null',ctx);
  await vm.runInContext('gmLoadBank()',ctx);
  console.log('bank',vm.runInContext('GMD.bank.length',ctx));
  const cnt={}; let bad=0;
  for(let d=0; d<28; d++){
    const day=new Date(Date.UTC(2026,9,19+d)).toISOString().slice(0,10);
    vm.runInContext(`gmDayKey=()=>"${day}"`,ctx);
    const run=async()=>JSON.stringify(await vm.runInContext(`(async()=>{const r=gmRng(gmHash('daily'+gmDayKey()));return (await gmBuildDaily(r)).map(x=>[x.id,x.c,x.t])})()`,ctx));
    const a=await run(), a2=await run();
    const arr=JSON.parse(a);
    if(a!==a2){console.log('DETERMINISTIK EMAS',day);bad++}
    if(arr.length!==5||new Set(arr.map(x=>x[0])).size!==5){console.log('5 ta emas/takror',day,arr.length);bad++}
    const label=vm.runInContext('gmDailyLabel()',ctx);
    if(d<7) console.log(day,new Date(day).getUTCDay(),label,'=>',arr.map(x=>x[1]+':'+x[2]).join(' '));
    arr.forEach(x=>cnt[x[1]]=(cnt[x[1]]||0)+1);
  }
  console.log('28 kunda mavzu taqsimoti:',JSON.stringify(cnt),'xato:',bad);
  if(Object.keys(cnt).length<10){console.log('hamma mavzu qamralmadi');bad++}
  process.exit(bad?1:0);
})().catch(e=>console.log('XATO',e.stack));
