/* v98 — 5D+4D+6D aralash tema: aurora fon, kartada tilt, tebranish. Mantiqqa tegmaydi. */
(function(){
  var d=document,de=d.documentElement;
  if((navigator.hardwareConcurrency||8)<=4||(navigator.deviceMemory||4)<=2)de.classList.add('lite');
  var a=d.createElement('div');a.className='aurora';a.innerHTML='<i></i><i></i><i></i>';
  (d.body||de).insertBefore(a,(d.body||de).firstChild);
  var tw=window.Telegram&&Telegram.WebApp;
  try{if(tw){tw.setHeaderColor&&tw.setHeaderColor('#06231a');tw.setBackgroundColor&&tw.setBackgroundColor('#06231a');tw.setBottomBarColor&&tw.setBottomBarColor('#0b3a2c')}}catch(e){}
  var SEL='.hbWrap>.hbCard,.result,.scoreBig,.hmCard';
  var reduce=matchMedia('(prefers-reduced-motion:reduce)').matches;
  function rst(e){e.style.transform=''}
  d.addEventListener('pointermove',function(ev){
    if(reduce)return;var e=ev.target.closest&&ev.target.closest(SEL);if(!e)return;
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
