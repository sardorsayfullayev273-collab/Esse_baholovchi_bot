/* v99 — YANGI ALIFBO: eski lotin alifbosidan yangisiga (G‘→Ğ, O‘→Ö, Sh→Ş, Ch→Ç) va teskari o‘tkazish. Mantiq mustaqil, boshqa kodga tegmaydi. */
(function(){
  var APOS="[‘ʻʼ'`´’′]";
  /* himoyalangan bo'laklar: havola, e-pochta, @username, #teg — o'zgartirilmaydi */
  var PROT=/(https?:\/\/\S+|www\.\S+|\S+@\S+\.\S+|[@#][A-Za-z0-9_]+)/g;
  function up(s){return s===s.toUpperCase()&&s!==s.toLowerCase()}
  function toNew(t){
    var n=0;
    function seg(s){
      s=s.replace(new RegExp('([GgOo])'+APOS,'g'),function(m,c){n++;return {G:'Ğ',g:'ğ',O:'Ö',o:'ö'}[c]});
      s=s.replace(/([Ss])([Hh])/g,function(m,a){n++;return a==='S'?'Ş':'ş'});
      s=s.replace(/([Cc])([Hh])/g,function(m,a){n++;return a==='C'?'Ç':'ç'});
      return s;
    }
    var out=t.split(PROT).map(function(p,i){return i%2?p:seg(p)}).join('');
    return {text:out,n:n};
  }
  function toOld(t){
    var n=0;
    function seg(s){
      return s.replace(/[ĞğÖöŞşÇç]/g,function(m,off,str){
        n++;
        var map={'Ğ':['G','‘'],'ğ':['g','‘'],'Ö':['O','‘'],'ö':['o','‘'],'Ş':['S','h'],'ş':['s','h'],'Ç':['C','h'],'ç':['c','h']};
        var r=map[m],base=r[0],tail=r[1];
        if(m===m.toUpperCase()){ /* bosh harf: qo'shni katta harf bo'lsa — hammasi katta (SH, CH, G‘, O‘) */
          var prev=str.charAt(off-1),next=str.charAt(off+1);
          if(up(prev)||up(next)) tail=tail==='h'?'H':tail;
        }
        return base+tail;
      });
    }
    var out=t.split(PROT).map(function(p,i){return i%2?p:seg(p)}).join('');
    return {text:out,n:n};
  }
  window.alifboConvert=function(t,dir){return dir==='old'?toOld(t||''):toNew(t||'')};

  /* ---------- sahifa ---------- */
  var S={dir:'new'};
  var SAMPLE='O‘zbekiston Respublikasida o‘zbek tili — davlat tili. Chiroyli she’r, tog‘ va shahar haqida suhbat. G‘oya, ishonch va chidam muhim.';
  function $(id){return document.getElementById(id)}
  function run(){
    var src=$('alfIn').value,r=window.alifboConvert(src,S.dir);
    $('alfOut').value=r.text;
    $('alfCnt').textContent=src.trim()?(r.n+' ta harf almashtirildi'):'Matn kiriting yoki namunani bosing';
  }
  function setDir(d){
    S.dir=d;
    document.querySelectorAll('#alifbo .alfSeg button').forEach(function(b){b.classList.toggle('on',b.dataset.d===d)});
    $('alfInL').textContent=d==='new'?'Eski alifbo (hozirgi)':'Yangi alifbo';
    $('alfOutL').textContent=d==='new'?'Yangi alifbo':'Eski alifbo (hozirgi)';
    run();
  }
  function copy(){
    var o=$('alfOut'),txt=o.value;if(!txt)return;
    function ok(){var b=$('alfCopy');var t=b.textContent;b.textContent='✅ Nusxalandi';setTimeout(function(){b.textContent=t},1400);
      try{if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.notificationOccurred('success')}catch(e){}}
    function fb(){try{o.focus();o.select();o.setSelectionRange(0,txt.length);document.execCommand('copy');ok()}catch(e){}}
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(ok,fb)}else fb();
  }
  function init(){
    if(!$('alfIn'))return;
    $('alfIn').addEventListener('input',run);
    $('alifbo').addEventListener('click',function(e){
      var b=e.target.closest('[data-d],[data-a]');if(!b)return;
      if(b.dataset.d)return setDir(b.dataset.d);
      var a=b.dataset.a;
      if(a==='sample'){$('alfIn').value=S.dir==='new'?SAMPLE:window.alifboConvert(SAMPLE,'new').text;run()}
      if(a==='clear'){$('alfIn').value='';run()}
      if(a==='copy')copy();
      if(a==='swap'){var v=$('alfOut').value;if(v){$('alfIn').value=v;setDir(S.dir==='new'?'old':'new')}}
    });
    setDir('new');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
