(function () {
  'use strict';

  var CLUSTER_COLORS = [
    '#FF2D8A','#D4AF37','#00C864','#FF8C00','#00BFFF',
    '#B44FE8','#FF6DB3','#F5D674','#00FF41','#4FC3F7','#FF5555'
  ];
  var K_REP_API = 1800, K_REP_CLUSTER = 5000, K_SPRING = 0.06, SPRING_LEN = 90;
  var DAMPING = 0.88, V_CAP = 8;

  var canvas, ctx, wrap, tooltip, nodes = [], W, H, cx, cy;
  var running = false, frameCount = 0, hoveredNode = null, resizeTimer;

  function ha(hex, a) {
    var r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }

  function buildGraph() {
    nodes = [];
    var clusters = window.API_CLUSTERS || [];
    var n = clusters.length;
    clusters.forEach(function(cl, ci) {
      var ang = (ci/n)*Math.PI*2, r = Math.min(W,H)*0.35;
      nodes.push({ id:'cluster-'+ci, type:'cluster', label:cl.name, icon:cl.icon,
        color:CLUSTER_COLORS[ci%CLUSTER_COLORS.length],
        x:cx+r*Math.cos(ang), y:cy+r*Math.sin(ang), vx:0, vy:0, radius:28, ci:ci });
    });
    clusters.forEach(function(cl, ci) {
      var clnd = nodes[ci];
      (cl.apis||[]).forEach(function(api, ai) {
        nodes.push({ id:'api-'+ci+'-'+ai, type:'api', name:api.name, url:api.url,
          shape:api.shape, notes:api.notes, auth:api.auth, status:api.status,
          color:CLUSTER_COLORS[ci%CLUSTER_COLORS.length], cid:'cluster-'+ci,
          x:clnd.x+(Math.random()-0.5)*40, y:clnd.y+(Math.random()-0.5)*40,
          vx:0, vy:0, radius:7, ci:ci });
      });
    });
  }

  function stepPhysics() {
    var i, j, a, b, dx, dy, dist, f, fx, fy;
    for (i=0; i<nodes.length; i++) {
      a=nodes[i];
      for (j=i+1; j<nodes.length; j++) {
        b=nodes[j];
        dx=b.x-a.x; dy=b.y-a.y;
        dist=Math.sqrt(dx*dx+dy*dy)||0.001;
        f=((a.type==='cluster'&&b.type==='cluster')?K_REP_CLUSTER:K_REP_API)/(dist*dist);
        fx=(dx/dist)*f; fy=(dy/dist)*f;
        a.vx-=fx; a.vy-=fy; b.vx+=fx; b.vy+=fy;
      }
    }
    for (i=0; i<nodes.length; i++) {
      a=nodes[i];
      if (a.type!=='api') continue;
      var cl=null;
      for (j=0;j<nodes.length;j++){ if(nodes[j].id===a.cid){cl=nodes[j];break;} }
      if (!cl) continue;
      dx=cl.x-a.x; dy=cl.y-a.y;
      dist=Math.sqrt(dx*dx+dy*dy)||0.001;
      f=K_SPRING*(dist-SPRING_LEN);
      fx=(dx/dist)*f; fy=(dy/dist)*f;
      a.vx+=fx; a.vy+=fy; cl.vx-=fx; cl.vy-=fy;
    }
    for (i=0; i<nodes.length; i++) {
      a=nodes[i];
      a.vx+=0.003*(cx-a.x); a.vy+=0.003*(cy-a.y);
      a.vx*=DAMPING; a.vy*=DAMPING;
      a.vx=Math.max(-V_CAP,Math.min(V_CAP,a.vx));
      a.vy=Math.max(-V_CAP,Math.min(V_CAP,a.vy));
      a.x+=a.vx; a.y+=a.vy;
    }
  }

  function render() {
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle='#0A0A0A'; ctx.fillRect(0,0,W,H);
    nodes.forEach(function(a) {
      if (a.type!=='api') return;
      var cl=null;
      for(var j=0;j<nodes.length;j++){if(nodes[j].id===a.cid){cl=nodes[j];break;}}
      if(!cl) return;
      ctx.beginPath(); ctx.moveTo(cl.x,cl.y); ctx.lineTo(a.x,a.y);
      ctx.strokeStyle=ha(a.color,0.12); ctx.lineWidth=0.8; ctx.stroke();
    });
    nodes.forEach(function(nd) {
      if (nd.type!=='api') return;
      var hov=hoveredNode&&hoveredNode.id===nd.id;
      var alpha=(nd.status==='idea'&&!hov)?0.38:0.75;
      ctx.beginPath(); ctx.arc(nd.x,nd.y,hov?nd.radius+2:nd.radius,0,Math.PI*2);
      ctx.fillStyle=ha(nd.color,alpha); ctx.fill();
      ctx.strokeStyle=ha(nd.color,0.9); ctx.lineWidth=1; ctx.stroke();
    });
    nodes.forEach(function(nd) {
      if (nd.type!=='cluster') return;
      var hov=hoveredNode&&hoveredNode.id===nd.id;
      ctx.beginPath(); ctx.arc(nd.x,nd.y,nd.radius,0,Math.PI*2);
      ctx.fillStyle=ha(nd.color,hov?0.55:0.35); ctx.fill();
      ctx.strokeStyle=nd.color; ctx.lineWidth=1.5; ctx.stroke();
      ctx.font='14px serif'; ctx.textAlign='center'; ctx.textBaseline='middle';
      ctx.fillStyle='#ffffff'; ctx.fillText(nd.icon,nd.x,nd.y-5);
      ctx.font='8px "Courier New"'; ctx.fillStyle=ha(nd.color,0.85);
      ctx.fillText(nd.label.toUpperCase(),nd.x,nd.y+18);
    });
  }

  function showTooltip(nd, mx, my) {
    var ac={none:'#00C864',free_key:'#D4AF37',free_tier:'#FF8C00'};
    var notes=nd.notes?(nd.notes.length>90?nd.notes.slice(0,90)+'…':nd.notes):'';
    tooltip.innerHTML='<span class="api-tooltip-name">'+nd.name+'</span>'+
      '<span class="api-tooltip-meta" style="color:'+(ac[nd.auth]||'#aaa')+'">'+nd.auth+' · '+nd.status+'</span>'+
      '<span class="api-tooltip-notes">'+notes+'</span>'+
      '<span class="api-tooltip-hint">click to open docs ↗</span>';
    var tx=mx+12, ty=my-10;
    if(tx+230>W) tx=mx-238; if(ty+80>H) ty=my-88;
    tooltip.style.left=tx+'px'; tooltip.style.top=ty+'px';
    tooltip.classList.add('visible');
  }

  function getPos(e) {
    var r=canvas.getBoundingClientRect();
    return {x:(e.clientX-r.left)*(W/r.width), y:(e.clientY-r.top)*(H/r.height)};
  }

  function tick() {
    if(!running) return;
    var steps=frameCount<300?3:1;
    for(var i=0;i<steps;i++) stepPhysics();
    frameCount++; render();
    requestAnimationFrame(tick);
  }

  function applySize() {
    var dpr=window.devicePixelRatio||1;
    W=wrap.clientWidth; H=Math.max(W*0.65,400); cx=W/2; cy=H/2;
    canvas.width=W*dpr; canvas.height=H*dpr;
    canvas.style.width=W+'px'; canvas.style.height=H+'px';
    ctx.setTransform(1,0,0,1,0,0); ctx.scale(dpr,dpr);
  }

  function init(canvasId) {
    canvas=document.getElementById(canvasId); ctx=canvas.getContext('2d');
    wrap=canvas.parentElement; tooltip=document.getElementById('graph-tooltip');
    wrap.style.position='relative';
    applySize(); buildGraph();
    canvas.addEventListener('mousemove',function(e){
      var pos=getPos(e), found=null;
      nodes.forEach(function(nd){
        var dx=nd.x-pos.x,dy=nd.y-pos.y;
        if(Math.sqrt(dx*dx+dy*dy)<nd.radius+4) found=nd;
      });
      hoveredNode=found;
      canvas.style.cursor=(found&&found.type==='api'&&found.url)?'pointer':'crosshair';
      if(found&&found.type==='api') showTooltip(found,pos.x,pos.y);
      else tooltip.classList.remove('visible');
    });
    canvas.addEventListener('click',function(e){
      var pos=getPos(e);
      nodes.forEach(function(nd){
        if(nd.type!=='api'||!nd.url) return;
        var dx=nd.x-pos.x,dy=nd.y-pos.y;
        if(Math.sqrt(dx*dx+dy*dy)<nd.radius+4) window.open(nd.url,'_blank','noopener');
      });
    });
    var ro=new ResizeObserver(function(){
      clearTimeout(resizeTimer);
      resizeTimer=setTimeout(function(){applySize();buildGraph();frameCount=0;},120);
    });
    ro.observe(wrap);
    running=true; requestAnimationFrame(tick);
  }

  function pause() { running=false; }
  function resume(){ if(!running){running=true;requestAnimationFrame(tick);} }

  window.ApiGraph={init:init,pause:pause,resume:resume};
}());
