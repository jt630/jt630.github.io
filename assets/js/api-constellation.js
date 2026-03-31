(function () {
  'use strict';

  var CLUSTER_COLORS = [
    '#FF2D8A','#D4AF37','#00C864','#FF8C00','#00BFFF',
    '#B44FE8','#FF6DB3','#F5D674','#00FF41','#4FC3F7','#FF5555'
  ];
  var HIT_RADIUS = 12, STAR_COUNT = 200;

  var canvas, ctx, wrap, tooltip;
  var W, H, running = false, hoveredApi = null, resizeTimer;
  var bgStars = [], positions = [], clusterMeta = [];

  function ha(hex, a) {
    var r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }

  function initStars() {
    bgStars = [];
    for (var i=0; i<STAR_COUNT; i++) {
      bgStars.push({ nx:Math.random(), ny:Math.random(),
        size:0.4+Math.random()*1.0, base:0.15+Math.random()*0.35,
        phase:Math.random()*Math.PI*2, speed:0.4+Math.random()*0.8 });
    }
  }

  function computeLayout() {
    var clusters = window.API_CLUSTERS || [];
    var cols=4, cellW=W/cols, cellH=H/3;
    positions=[]; clusterMeta=[];
    clusters.forEach(function(cl, ci) {
      var cellIdx = ci<5 ? ci : ci+1;
      var col=cellIdx%cols, row=Math.floor(cellIdx/cols);
      var ax=col*cellW+cellW/2, ay=row*cellH+cellH/2;
      var color=CLUSTER_COLORS[ci%CLUSTER_COLORS.length];
      var apis=cl.apis||[], n=apis.length;
      var r=Math.min(cellW,cellH)*0.32;
      var pts=apis.map(function(api,ai){
        var angle=(ai/n)*Math.PI*2+ci*0.3;
        return { x:ax+r*Math.cos(angle), y:ay+r*Math.sin(angle), api:api, ci:ci };
      });
      var minY=pts.length ? pts.reduce(function(m,p){return Math.min(m,p.y);},Infinity) : ay;
      clusterMeta.push({ ax:ax, ay:ay, labelX:ax, labelY:minY-14,
        color:color, name:cl.name, icon:cl.icon, pts:pts });
      pts.forEach(function(p){ positions.push(p); });
    });
  }

  function drawBgStars(now) {
    bgStars.forEach(function(s){
      var alpha=s.base+0.15*Math.sin(now*0.001*s.speed+s.phase);
      ctx.beginPath(); ctx.arc(s.nx*W,s.ny*H,s.size,0,Math.PI*2);
      ctx.fillStyle='rgba(255,255,255,'+alpha+')'; ctx.fill();
    });
  }

  function drawStar(p, color, hov) {
    var gr=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,hov?16:10);
    gr.addColorStop(0,ha(color,hov?0.55:0.30)); gr.addColorStop(1,'rgba(0,0,0,0)');
    ctx.beginPath(); ctx.arc(p.x,p.y,hov?16:10,0,Math.PI*2);
    ctx.fillStyle=gr; ctx.fill();
    if (hov) {
      ctx.beginPath(); ctx.arc(p.x,p.y,7,0,Math.PI*2);
      ctx.strokeStyle=color; ctx.lineWidth=1.2; ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(p.x,p.y,hov?4:3,0,Math.PI*2);
    ctx.fillStyle=hov?'#ffffff':'rgba(255,255,255,0.85)'; ctx.fill();
  }

  function drawConstellations() {
    clusterMeta.forEach(function(cm){
      var pts=cm.pts; if(!pts.length) return;
      ctx.beginPath();
      pts.forEach(function(p,i){
        var nx=pts[(i+1)%pts.length];
        if(i===0) ctx.moveTo(p.x,p.y); else ctx.lineTo(p.x,p.y);
        ctx.lineTo(nx.x,nx.y);
      });
      ctx.strokeStyle='rgba(212,175,55,0.10)'; ctx.lineWidth=0.7; ctx.stroke();
      ctx.font='10px "Courier New"'; ctx.textAlign='center'; ctx.textBaseline='bottom';
      ctx.fillStyle=ha(cm.color,0.6);
      ctx.fillText(cm.icon+' '+cm.name.toUpperCase(),cm.labelX,cm.labelY);
      pts.forEach(function(p){
        if(p===hoveredApi) return;
        drawStar(p,cm.color,false);
      });
    });
    if (hoveredApi) {
      var cm2=clusterMeta[hoveredApi.ci];
      if(cm2) drawStar(hoveredApi,cm2.color,true);
    }
  }

  function showTooltip(p, mx, my) {
    var api=p.api;
    var ac={none:'#00C864',free_key:'#D4AF37',free_tier:'#FF8C00'};
    var notes=api.notes?(api.notes.length>80?api.notes.slice(0,80)+'…':api.notes):'';
    tooltip.innerHTML='<span class="api-tooltip-name">'+api.name+'</span>'+
      '<span class="api-tooltip-meta" style="color:'+(ac[api.auth]||'#aaa')+'">'+api.auth+' · '+api.status+'</span>'+
      '<span class="api-tooltip-notes">'+notes+'</span>'+
      '<span class="api-tooltip-hint">click to open docs ↗</span>';
    var tx=mx+14, ty=my-10;
    if(tx+220>W) tx=mx-228; if(ty+80>H) ty=my-88;
    tooltip.style.left=tx+'px'; tooltip.style.top=ty+'px';
    tooltip.classList.add('visible');
  }

  function getPos(e) {
    var r=canvas.getBoundingClientRect();
    return {x:(e.clientX-r.left)*(W/r.width), y:(e.clientY-r.top)*(H/r.height)};
  }

  function tick() {
    if(!running) return;
    var now=Date.now();
    ctx.clearRect(0,0,W,H); ctx.fillStyle='#0A0A0A'; ctx.fillRect(0,0,W,H);
    drawBgStars(now); drawConstellations();
    requestAnimationFrame(tick);
  }

  function applySize() {
    var dpr=window.devicePixelRatio||1;
    W=wrap.clientWidth; H=Math.max(W*0.65,400);
    canvas.width=W*dpr; canvas.height=H*dpr;
    canvas.style.width=W+'px'; canvas.style.height=H+'px';
    ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr,dpr);
  }

  function init(canvasId) {
    canvas=document.getElementById(canvasId); ctx=canvas.getContext('2d');
    wrap=canvas.parentElement; tooltip=document.getElementById('constellation-tooltip');
    wrap.style.position='relative';
    applySize(); initStars(); computeLayout();
    canvas.addEventListener('mousemove',function(e){
      var pos=getPos(e), found=null;
      positions.forEach(function(p){
        var dx=p.x-pos.x,dy=p.y-pos.y;
        if(Math.sqrt(dx*dx+dy*dy)<HIT_RADIUS) found=p;
      });
      hoveredApi=found; canvas.style.cursor=found?'pointer':'crosshair';
      if(found) showTooltip(found,pos.x,pos.y);
      else tooltip.classList.remove('visible');
    });
    canvas.addEventListener('click',function(e){
      var pos=getPos(e);
      positions.forEach(function(p){
        if(!p.api.url) return;
        var dx=p.x-pos.x,dy=p.y-pos.y;
        if(Math.sqrt(dx*dx+dy*dy)<HIT_RADIUS) window.open(p.api.url,'_blank','noopener');
      });
    });
    var ro=new ResizeObserver(function(){
      clearTimeout(resizeTimer);
      resizeTimer=setTimeout(function(){applySize();computeLayout();},120);
    });
    ro.observe(wrap);
    running=true; requestAnimationFrame(tick);
  }

  function pause() { running=false; }
  function resume(){ if(!running){running=true;requestAnimationFrame(tick);} }

  window.ApiConstellation={init:init,pause:pause,resume:resume};
}());
