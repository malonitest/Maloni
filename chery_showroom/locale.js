// Shared display strings; dynamic conversation text is localized by the controller.
let localeData={ui:{}},displayLanguage='en',lastApplied='';
const originalLocaleText=new WeakMap(),originalLocaleAttributes=new WeakMap();
function L(text){return displayLanguage==='cs'?(localeData.ui[text]||text):text;}
function applyShowroomLanguage(language,force=false){
  displayLanguage=language==='cs'?'cs':'en';document.documentElement.lang=displayLanguage;
  if(lastApplied===displayLanguage&&!force)return;lastApplied=displayLanguage;
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;
  while(node=walker.nextNode()){
    if(node.parentElement?.closest('script,style,#log,#error,#state,#handoff,#concierge-answer,#demoSubtitle,#interactiveStatus,#conversationState'))continue;
    const original=originalLocaleText.get(node)??node.textContent;originalLocaleText.set(node,original);
    const value=original.trim();if(localeData.ui[value])node.textContent=original.replace(value,L(value));
  }
  document.querySelectorAll('[placeholder],[aria-label],[title]').forEach(element=>{
    let values=originalLocaleAttributes.get(element);
    if(!values){values={};for(const key of ['placeholder','aria-label','title'])if(element.hasAttribute(key))values[key]=element.getAttribute(key);originalLocaleAttributes.set(element,values);}
    for(const [key,value] of Object.entries(values))element.setAttribute(key,L(value));
  });
}
fetch('/messages.json').then(response=>{if(!response.ok)throw Error('Locale unavailable');return response.json();}).then(value=>{localeData=value;applyShowroomLanguage(displayLanguage,true);}).catch(()=>{});
