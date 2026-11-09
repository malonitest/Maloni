function updateInteractive(s){
 const v=s.interactive;if(!v)return;
 const labels={idle:'Ready',arrival:'Customer arriving',choose:'Choose a car',offer:'Waiting for consent',escort:'Escort to the car',paused:'Visit paused',presentation:'Presentation',questions:'Customer questions',declined:'Offer declined',handoff:'Salesperson summary',leaving:'Customer leaving',returning:'Returning to reception',completed:'Visit completed'};
 document.getElementById('interactiveStatus').textContent=L(s.ready_for_visit?'Ready':labels[v.stage]||v.stage)+(v.stage==='presentation'?' '+(v.presentation_part+1)+'/3':'')+(v.reason?' · '+v.reason:'');
 document.querySelectorAll('[data-customer]').forEach(b=>b.disabled=!v.active);
 document.querySelectorAll('[data-choice]').forEach(b=>b.disabled=!v.active||!v.available_choices.includes(b.dataset.choice));
 document.getElementById('automaticVisitCamera').checked=v.auto_camera;
}
