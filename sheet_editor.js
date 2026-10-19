export default function({parentElement, data, setStateValue}) {
  const root=parentElement.querySelector('.wire-sheet');
  let rows=structuredClone(data.rows), selected=0, separateStrip=false, deletion=false;
  const colors=Object.fromEntries(data.palette.map(c=>[c.name,c.background]));
  const text=v=>v===null||v===undefined?'':String(v);
  const make=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e;};
  const emit=()=>{setStateValue('rows',structuredClone(rows));const s=root.querySelector('.status');if(s)s.textContent='草稿已更新 · 按下方「儲存紀錄」保存全部線材';};
  const groups=()=>{const g=new Map();for(const row of rows){const id=text(row['電纜編號']||row['線號']);if(!g.has(id))g.set(id,[]);g.get(id).push(row);}return [...g.entries()];};
  const button=(label,action,cls)=>{const b=make('button',label,cls);b.type='button';b.onclick=action;return b;};
  const input=(label,value,onchange,type='text',options=null)=>{
    const e=make(options?'select':'input');e.setAttribute('aria-label',label);
    if(options){if(value&&!options.includes(value))options=[value,...options];for(const option of options){const o=make('option',option);o.value=option;e.append(o);}}
    else {e.type=type;if(type==='number'){e.min='0';e.step='any';}}
    e.value=text(value);e.oninput=()=>{onchange(e.value);emit();};return e;
  };
  const field=(label,value,change,type='text',options=null)=>{const l=make('label',undefined,'field');l.append(make('span',label),input(label,value,change,type,options));return l;};
  const nextLine=()=>{let n=1;const used=new Set(rows.map(r=>text(r['線號']).toLowerCase()));while(used.has('w'+String(n).padStart(3,'0')))n++;return 'W'+String(n).padStart(3,'0');};
  const nextCable=()=>{let n=1;const used=new Set(groups().map(g=>g[0].toLowerCase()));while(used.has('cbl-'+String(n).padStart(3,'0')))n++;return 'CBL-'+String(n).padStart(3,'0');};
  const emptyRow=()=>{const r=Object.fromEntries(data.fields.map(f=>[f,'']));for(const end of ['起點','終點'])Object.assign(r,{[end+'接頭類型']:'無',[end+'端接方式']:'未指定',[end+'接點形式']:'未指定'});return Object.assign(r,{'線號':nextLine(),'芯線識別方式':'印字號碼','配線狀態':data.states[0],'查驗結果':data.checks[0]});};
  const addCable=(copy=false)=>{const all=groups(),id=nextCable();let source=copy&&all[selected]?all[selected][1]:null;
    if(source){for(const old of source){const r=structuredClone(old);r['線號']=nextLine();r['電纜編號']=r['線材結構']==='單芯線'?'':id;rows.push(r);}}
    else {const r=emptyRow();Object.assign(r,{'電纜編號':id,'線材結構':'多芯電纜','電纜總芯數':2,'芯線編號':'01'});rows.push(r);const b=emptyRow();Object.assign(b,{'電纜編號':id,'線材結構':'多芯電纜','電纜總芯數':2,'芯線編號':'02'});rows.push(b);}
    selected=groups().length-1;separateStrip=false;deletion=false;emit();render();
  };
  function colorMenu(row, mirror=false){
    const wrap=make('div',undefined,'identity');const details=make('details',undefined,'color-menu');const summary=make('summary',undefined,'color-summary');
    summary.setAttribute('aria-label',row['線號']+(mirror?' 終點':'')+' 線色色卡');
    const chip=make('span',undefined,'swatch'),name=make('span');
    const update=()=>{chip.style.background=colors[row['線色']]||'transparent';name.textContent=row['線色']||'選色';};update();summary.append(chip,name);details.append(summary);
    const cards=make('div',undefined,'cards');cards.setAttribute('role','listbox');cards.setAttribute('aria-label',row['線號']+' 64色色卡');
    data.palette.forEach((color,index)=>{const b=button('',()=>{row['線色']=color.name;if(row['芯線編號'])row['芯線識別方式']='號碼＋顏色';else row['芯線識別方式']='顏色';emit();render();});b.className='card';b.title=color.name;b.setAttribute('aria-label',color.name);b.setAttribute('role','option');b.setAttribute('aria-selected',String(row['線色']===color.name));const sw=make('span',undefined,'swatch');sw.style.background=color.background;b.append(sw);
      b.onkeydown=e=>{if(e.key==='Escape'){details.open=false;summary.focus();return;}const n={ArrowRight:1,ArrowLeft:-1,ArrowUp:-8,ArrowDown:8}[e.key];if(n!==undefined){e.preventDefault();cards.children[(index+n+64)%64].focus();}};cards.append(b);});
    cards.append(button('清除顏色',()=>{row['線色']='';row['芯線識別方式']='印字號碼';emit();render();},'clear'));
    details.append(cards);details.ontoggle=()=>{if(details.open)root.querySelectorAll('.color-menu').forEach(d=>{if(d!==details)d.open=false;});};wrap.append(details);
    const printed=input(row['線號']+(mirror?' 終點':'')+' 芯線印字',row['芯線編號'],v=>{row['芯線編號']=v;row['芯線識別方式']=v?(row['線色']?'號碼＋顏色':'印字號碼'):'顏色';sync(row,'芯線編號',v);});printed.placeholder='線上號碼';printed.dataset.row=row['線號'];printed.dataset.field='芯線編號';wrap.append(printed);
    const hint=row['線材結構']==='雙絞電纜'?`${row['對絞組號']} / ${row['對內芯別']}`:row['線號'];wrap.append(make('span',hint,'mirror'));return wrap;
  }
  function sync(row,key,value){root.querySelectorAll('[data-row][data-field]').forEach(e=>{if(e.dataset.row===row['線號']&&e.dataset.field===key&&e.value!==text(value))e.value=text(value);});}
  function render(){
    root.replaceChildren();const all=groups();if(selected>=all.length)selected=Math.max(0,all.length-1);
    const toolbar=make('div',undefined,'toolbar');if(all.length){const chooser=input('選擇線材',String(selected),()=>{},'text',all.map((_,i)=>String(i)));chooser.replaceChildren();all.forEach(([id,members],i)=>{const o=make('option',`${i+1}. ${id} · ${members[0]['迴路／用途']||'未填用途'} · ${members.length} 芯`);o.value=String(i);chooser.append(o);});chooser.value=String(selected);chooser.oninput=null;chooser.onchange=()=>{selected=Number(chooser.value);separateStrip=false;deletion=false;render();};toolbar.append(chooser);}
    toolbar.append(button('＋ 新增線材',()=>addCable(), 'primary'));if(all.length)toolbar.append(button('複製這條線材',()=>addCable(true)));toolbar.append(make('span',`${all.length} 條線材 · ${rows.length} 芯`,'muted'));root.append(toolbar);
    if(!all.length){root.append(make('div','按「新增線材」開始；一條線一張表，左右端一起填。','empty'));return;}
    const [id,members]=all[selected],first=members[0];const shared=(f,v)=>{members.forEach(r=>r[f]=v);syncShared(f,v);};
    function syncShared(f,v){root.querySelectorAll('[data-shared]').forEach(e=>{if(e.dataset.shared===f&&e.value!==text(v))e.value=text(v);});}
    const title=make('div',undefined,'titlebar');title.append(make('h3',`${id}　${first['迴路／用途']||'線材製作表'}`),make('span',`${members.length} 芯 · 長度 cm / 剝皮 mm`,'badge'));root.append(title);
    const common=make('div',undefined,'common');
    common.append(field('線材／電纜編號',id,v=>{const collision=groups().some(([other])=>other!==id&&other.toLowerCase()===v.trim().toLowerCase());if(!v.trim()||collision){error.textContent='編號不可空白或與其他線材重複。';return;}error.textContent='';if(first['線材結構']==='單芯線')first['線號']=v.trim();else shared('電纜編號',v.trim());}));
    common.append(field('線材結構',first['線材結構'],v=>{if(v==='單芯線'&&members.length>1){error.textContent='請先刪至一芯，再改為單芯線。';root.querySelector('[aria-label="線材結構"]').value=first['線材結構'];return;}if(v==='單芯線')first['電纜編號']='';else if(!first['電纜編號'])shared('電纜編號',id);shared('線材結構',v);if(v==='雙絞電纜')members.forEach((r,i)=>{r['對絞組號']=`P${String(Math.floor(i/2)+1).padStart(2,'0')}`;r['對內芯別']='AB'[i%2];});else members.forEach(r=>{r['對絞組號']='';r['對內芯別']='';});if(v!=='單芯線'&&members.length===1)resize(2);else {emit();render();}},'text',data.structures));
    const count=field('電纜總芯數（改完直接展開）',first['電纜總芯數']||members.length,()=>{},'number');const countInput=count.querySelector('input');countInput.min=first['線材結構']==='單芯線'?'1':'2';countInput.max='512';countInput.step='1';let countTimer;
    const commitCount=()=>{clearTimeout(countTimer);if(countInput.isConnected)resize(Number(countInput.value));};
    countInput.oninput=()=>{clearTimeout(countTimer);countTimer=setTimeout(commitCount,450);};countInput.onchange=commitCount;countInput.onblur=commitCount;countInput.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();commitCount();}};common.append(count);
    common.append(field('迴路／用途',first['迴路／用途'],v=>shared('迴路／用途',v)),field('芯線線徑（mm²）',first['線徑（mm²）'],v=>shared('線徑（mm²）',v),'number'));root.append(common);
    const ends=make('div',undefined,'endpoints');for(const end of ['起點','終點'])ends.append(field(`${end}設備／位置`,first[end+'設備'],v=>shared(end+'設備',v)));root.append(ends);
    const error=make('p','','error');root.append(error);
    function resize(n){
      if(n===members.length&&Number(first['電纜總芯數'])===n)return;
      const min=first['線材結構']==='單芯線'?1:2;
      if(!Number.isInteger(n)||n<min||n>512||(min===1&&n!==1)){error.textContent='單芯線請填 1；多芯／雙絞線請填 2～512 的整數。';return;}
      if(n<members.length){error.textContent=`已有 ${members.length} 芯。請用「刪除最後一芯」逐芯確認，再降低芯數。`;return;}
      const sharedFields=['電纜編號','線材結構','迴路／用途','線材型號','線徑（mm²）','長度（cm）','浪管規格','浪管長度（cm）'];
      for(const end of ['起點','終點'])for(const suffix of ['設備','導體剝皮（mm）','外被剝除（mm）','接頭類型','接頭代號','接頭型號','端接方式','尾夾／拉力固定'])if(members.every(r=>text(r[end+suffix])===text(first[end+suffix])))sharedFields.push(end+suffix);
      const usedCores=new Set(members.map(r=>text(r['芯線編號']))),usedPairs=new Set(members.map(r=>r['對絞組號']+'/'+r['對內芯別']));
      while(members.length<n){const r=emptyRow();sharedFields.forEach(f=>r[f]=first[f]);let c=1;while(usedCores.has(String(c).padStart(2,'0')))c++;r['芯線編號']=String(c).padStart(2,'0');usedCores.add(r['芯線編號']);if(first['線材結構']==='雙絞電纜'){let p=0;while(usedPairs.has(`P${String(Math.floor(p/2)+1).padStart(2,'0')}/${'AB'[p%2]}`))p++;r['對絞組號']=`P${String(Math.floor(p/2)+1).padStart(2,'0')}`;r['對內芯別']='AB'[p%2];usedPairs.add(r['對絞組號']+'/'+r['對內芯別']);}rows.push(r);members.push(r);}
      shared('電纜總芯數',n);emit();render();
    }
    const actions=make('div',undefined,'actions');const check=make('label');const cb=make('input');cb.type='checkbox';cb.checked=separateStrip;cb.onchange=()=>{separateStrip=cb.checked;render();};check.append(cb,make('span','剝皮長度分芯填寫'));actions.append(check);
    for(const end of ['起點','終點'])actions.append(button(`${end}端子向下填滿`,()=>{shared(end+'端末',first[end+'端末']);emit();render();}));
    actions.append(button('起點號碼圈複製到終點',()=>{members.forEach(r=>r['終點號碼圈']=r['起點號碼圈']);emit();render();}));
    if(members.length>1)actions.append(button('刪除最後一芯',()=>{deletion='core';render();},'danger'));
    actions.append(button('刪除這條線材',()=>{deletion='cable';render();},'danger'));root.append(actions);
    if(deletion){const notice=make('div',undefined,'actions');notice.append(make('span',deletion==='core'?`確定刪除 ${members.at(-1)['線號']}？`:`確定刪除 ${id} 全部 ${members.length} 芯？`),button('確定刪除',()=>{const discard=new Set(deletion==='core'?[members.at(-1)]:members);rows=rows.filter(r=>!discard.has(r));if(deletion==='core')members.slice(0,-1).forEach(r=>r['電纜總芯數']=members.length-1);deletion=false;emit();render();},'danger'),button('取消',()=>{deletion=false;render();}));root.append(notice);}
    root.append(make('p','直接點格子填寫；Tab 移到下一格。端子格上方填料號，下方填端子編號／接頭 pin。一般端子可留空 pin；軍規／動力接頭需填腳位。','help'));
    const scroller=make('div',undefined,'scroll'),table=make('table',undefined,'sheet');table.setAttribute('aria-label','線材製作編輯表');
    const widths=[84,73,66,128,106,108,72,78,72,84,73,66,128,106];const colgroup=make('colgroup');widths.forEach(w=>{const c=make('col');c.style.width=(w/widths.reduce((a,b)=>a+b,0)*100)+'%';colgroup.append(c);});table.append(colgroup);
    const thead=make('thead'),bands=make('tr',undefined,'bands');[['起點加工',5],['線材共用資料',4],['終點加工',5]].forEach(([label,n])=>{const th=make('th',label);th.colSpan=n;bands.append(th);});thead.append(bands);
    const hr=make('tr',undefined,'headers');['顏色／印字','號碼圈','剝皮','端子／pin','接頭','線材規格','線材長度','浪管規格','浪管長度','顏色／印字','號碼圈','剝皮','端子／pin','接頭'].forEach((label,i)=>{const th=make('th',label);if([2,11].includes(i))th.append(make('small','mm'));if([6,8].includes(i))th.append(make('small','cm'));hr.append(th);});thead.append(hr);table.append(thead);const tbody=make('tbody');table.append(tbody);
    const setCell=(tr,row,f,options={})=>{const td=make('td',undefined,options.shared?'common-cell':'');if(options.shared)td.rowSpan=members.length;
      const value=options.value===undefined?row[f]:options.value;let editor;
      const change=v=>{if(options.shared)shared(f,v);else {row[f]=v;sync(row,f,v);}};
      if(f.endsWith('接頭型號')){editor=make('textarea');editor.setAttribute('aria-label',options.label||`${row['線號']} ${f}`);editor.value=text(value);editor.rows=3;editor.oninput=()=>{change(editor.value);emit();};}
      else editor=input(options.label||`${row['線號']} ${f}`,value,change,options.number?'number':'text');
      if(options.shared)editor.dataset.shared=f;else {editor.dataset.row=row['線號'];editor.dataset.field=f;}td.append(editor);tr.append(td);return td;};
    members.forEach((row,i)=>{const tr=make('tr');tbody.append(tr);const l=make('td');l.append(colorMenu(row));tr.append(l);setCell(tr,row,'起點號碼圈');
      const sameStrip=members.every(r=>text(r['起點導體剝皮（mm）'])===text(first['起點導體剝皮（mm）']));if(separateStrip||!sameStrip||i===0)setCell(tr,row,'起點導體剝皮（mm）',{shared:!separateStrip&&sameStrip,number:true,label:!separateStrip&&sameStrip?'起點共用剝皮（mm）':undefined});
      const left=setCell(tr,row,'起點端末');left.firstChild.className='part';left.firstChild.placeholder='端子料號';const lp=input(`${row['線號']} 起點端子／pin`,row['起點端子'],v=>row['起點端子']=v);lp.className='pin';lp.placeholder='端子編號／pin';left.append(lp);
      const sameConnector=members.every(r=>text(r['起點接頭型號'])===text(first['起點接頭型號']));if(!sameConnector||i===0)setCell(tr,row,'起點接頭型號',{shared:sameConnector,label:sameConnector?'起點共用接頭':undefined});
      if(i===0){setCell(tr,first,'線材型號',{shared:true,label:'共用線材規格'});setCell(tr,first,'長度（cm）',{shared:true,number:true,label:'共用線材長度（cm）'});setCell(tr,first,'浪管規格',{shared:true,label:'共用浪管規格'});setCell(tr,first,'浪管長度（cm）',{shared:true,number:true,label:'共用浪管長度（cm）'});}
      const rightIdentity=make('td');rightIdentity.append(colorMenu(row,true));tr.append(rightIdentity);setCell(tr,row,'終點號碼圈');
      const rightStrip=members.every(r=>text(r['終點導體剝皮（mm）'])===text(first['終點導體剝皮（mm）']));if(separateStrip||!rightStrip||i===0)setCell(tr,row,'終點導體剝皮（mm）',{shared:!separateStrip&&rightStrip,number:true,label:!separateStrip&&rightStrip?'終點共用剝皮（mm）':undefined});
      const right=setCell(tr,row,'終點端末');right.firstChild.className='part';right.firstChild.placeholder='端子料號';const rp=input(`${row['線號']} 終點端子／pin`,row['終點端子'],v=>row['終點端子']=v);rp.className='pin';rp.placeholder='端子編號／pin';right.append(rp);
      const rc=members.every(r=>text(r['終點接頭型號'])===text(first['終點接頭型號']));if(!rc||i===0)setCell(tr,row,'終點接頭型號',{shared:rc,label:rc?'終點共用接頭':undefined});
    });scroller.append(table);root.append(scroller);
    const advanced=make('details',undefined,'advanced');advanced.append(make('summary','軍規／動力接頭、雙絞分組與其他加工'));root.append(advanced);
    const coreChoice=input('進階加工芯線',first['線號'],()=>{},'text',members.map(r=>r['線號']));coreChoice.className='core-choice';advanced.append(coreChoice);const detailBody=make('div');advanced.append(detailBody);
    function showDetails(){detailBody.replaceChildren();const row=members.find(r=>r['線號']===coreChoice.value)||first;const base=make('div',undefined,'footer-fields');base.append(field('芯線識別方式',row['芯線識別方式'],v=>row['芯線識別方式']=v,'text',data.identifiers),field('對絞組號',row['對絞組號'],v=>row['對絞組號']=v),field('對內芯別',row['對內芯別'],v=>row['對內芯別']=v,'text',['','A','B']));detailBody.append(base);
      const grid=make('div',undefined,'details-grid');for(const end of ['起點','終點']){const section=make('div',undefined,'detail-fields');section.append(make('h4',end+'接頭加工'));
        for(const suffix of ['設備','外被剝除（mm）','接頭類型','接頭代號','接點形式','接點料號','端接方式','熱縮套管','屏蔽／接地處理','尾夾／拉力固定','作業圖號／規範','加工要求']){const key=end+suffix;const opts={'接頭類型':data.connectors,'接點形式':data.contacts,'端接方式':data.terminations}[suffix];section.append(field(key,row[key],v=>{if(suffix==='外被剝除（mm）')shared(key,v);else row[key]=v;},suffix.includes('mm')?'number':'text',opts));}
        section.append(button(`將此芯${end}接頭加工套用整條線`,()=>{for(const suffix of ['外被剝除（mm）','接頭類型','接頭代號','接頭型號','接點形式','接點料號','端接方式','熱縮套管','屏蔽／接地處理','尾夾／拉力固定','作業圖號／規範','加工要求'])shared(end+suffix,row[end+suffix]);emit();}));grid.append(section);
      }detailBody.append(grid);const status=make('div',undefined,'footer-fields');status.append(field('配線狀態',row['配線狀態'],v=>row['配線狀態']=v,'text',data.states),field('查驗結果',row['查驗結果'],v=>row['查驗結果']=v,'text',data.checks),field('備註',row['備註'],v=>row['備註']=v));detailBody.append(status);
    }coreChoice.oninput=null;coreChoice.onchange=showDetails;showDetails();
    root.append(make('p','草稿保留在目前頁面 · 最後按「儲存紀錄」一次保存全部線材','status'));
    // Paste a copied column into matching core rows; common cells remain shared.
    root.querySelectorAll('td input[data-row][data-field]').forEach(el=>{el.onpaste=e=>{
      const content=e.clipboardData.getData('text');
      if(!content.includes('\n'))return;
      if(content.includes('\t')){e.preventDefault();error.textContent='請一次貼上一欄資料；可從 Excel 複製同一欄的多列。';return;}
      e.preventDefault();const from=members.findIndex(r=>r['線號']===el.dataset.row);
      content.replace(/\r/g,'').replace(/\n$/,'').split('\n').forEach((v,i)=>{const row=members[from+i];if(row){row[el.dataset.field]=v;if(el.dataset.field==='芯線編號')row['芯線識別方式']=v?(row['線色']?'號碼＋顏色':'印字號碼'):'顏色';}});
      emit();render();
    };});
  }
  render();
}
