/* v98 — tema A (Och mint): kartada tilt, tebranish, YENGIL REJIM (avto + qo'lda). */
(function(){
  var d=document,de=d.documentElement,KEY='theme_lite';
  function pref(){try{return localStorage.getItem(KEY)}catch(e){return null}}
  function save(v){try{localStorage.setItem(KEY,v)}catch(e){}}
  function setLite(on){de.classList.toggle('lite',!!on);var t=d.getElementById('tglLite');if(t)t.textContent=on?'🐢 Yengil':'✨ To‘liq'}
  var p=pref();
  /* 1) qo'lda tanlov eng ustun; 2) taxmin; 3) haqiqiy tezlik o'lchovi */
  var guess=(navigator.hardwareConcurrency||8)<=4||(navigator.deviceMemory||4)<=2||matchMedia('(prefers-reduced-motion:reduce)').matches||(navigator.connection&&navigator.connection.saveData);
  setLite(p?p==='1':guess);
  /* FPS probe: ~0.9 s ichida kadr tezligi; 40 dan past bo'lsa avtomatik yengil rejim (faqat qo'lda tanlanmagan bo'lsa) */
  if(!p&&!de.classList.contains('lite')){
    var n=0,t0=0,probe=function(t){
      if(!t0)t0=t;n++;
      if(t-t0<900)return requestAnimationFrame(probe);
      var fps=n*1000/(t-t0);
      if(fps<40){setLite(true);save('1')}
    };
    setTimeout(function(){requestAnimationFrame(probe)},1200); /* yuklanish tugagach */
  }
  /* sahifa ko'rinmay qolsa animatsiya to'xtaydi (batareya) */
  
  /* qo'lda almashtirish tugmasi (sarlavhada) */
  function addBtn(){
    var h=d.querySelector('.app');if(!h||d.getElementById('tglLite'))return;
    var b=d.createElement('button');b.id='tglLite';b.className='tgl';b.type='button';
    b.onclick=function(e){e.stopPropagation();var on=!de.classList.contains('lite');setLite(on);save(on?'1':'0')};
    h.appendChild(b);setLite(de.classList.contains('lite'));
  }
  if(d.readyState==='loading')d.addEventListener('DOMContentLoaded',addBtn);else addBtn();
  var tw=window.Telegram&&Telegram.WebApp;
  try{if(tw){tw.setHeaderColor&&tw.setHeaderColor('#08402f');tw.setBackgroundColor&&tw.setBackgroundColor('#eaf5ef');tw.setBottomBarColor&&tw.setBottomBarColor('#eaf5ef')}}catch(e){}
  var SEL='.hbWrap>.hbCard,.result,.scoreBig,.hmCard';
  var reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  function rst(e){e.style.transform=''}
  d.addEventListener('pointermove',function(ev){
    if(reduce||de.classList.contains('lite'))return;var e=ev.target.closest&&ev.target.closest(SEL);if(!e)return;
    e.classList.add('tiltK');var r=e.getBoundingClientRect();
    var x=(ev.clientX-r.left)/r.width-.5,y=(ev.clientY-r.top)/r.height-.5;
    e.style.transform='perspective(800px) rotateX('+(-y*9).toFixed(1)+'deg) rotateY('+(x*11).toFixed(1)+'deg)';
  },{passive:true});
  ['pointerup','pointercancel','pointerleave'].forEach(function(t){d.addEventListener(t,function(ev){
    var e=ev.target.closest&&ev.target.closest(SEL);if(e)rst(e)},true)});
  d.addEventListener('click',function(ev){
    if(!ev.target.closest||!ev.target.closest('button,.opt,.sopt'))return;
    try{if(tw&&tw.HapticFeedback)tw.HapticFeedback.selectionChanged();else if(navigator.vibrate)navigator.vibrate(6)}catch(e){}
  },true);
})();
