// Browser transport only; every accepted transcript goes through the local controller.
(function(root) {
  class BrowserVoice {
    constructor({environment=root, onTranscript, onError=()=>{}, onListening=()=>{}}) {
      this.env=environment;this.onTranscript=onTranscript;this.onError=onError;
      this.onListening=onListening;this.recognition=null;this.generation=0;
    }
    stopListening() {
      ++this.generation;
      const recognition=this.recognition;this.recognition=null;
      if(recognition) {try {recognition.abort();} catch(_) {}}
      this.onListening(false);
    }
    cancel() {this.stopListening();this.env.speechSynthesis?.cancel();}
    listen(isCurrent=()=>true,language='en') {
      this.cancel();
      const Recognition=this.env.SpeechRecognition||this.env.webkitSpeechRecognition;
      if(!Recognition) {this.onError('Speech recognition is unavailable. Please type instead.');return false;}
      const generation=this.generation;
      let recognition;
      try {
        recognition=new Recognition();this.recognition=recognition;
        recognition.lang=language==='cs'?'cs-CZ':'en-US';recognition.continuous=false;recognition.interimResults=false;
        let accepted=false;
        const current=()=>this.recognition===recognition&&generation===this.generation&&isCurrent();
        recognition.onresult=event=>{
          if(!current()||accepted)return;
          const result=event.results?.[event.resultIndex||0];
          const text=result?.[0]?.transcript;
          if(result?.isFinal===false||typeof text!=='string'||!text.trim())return;
          accepted=true;this.stopListening();this.onTranscript(text.trim());
        };
        recognition.onerror=event=>{
          if(!current())return;
          this.stopListening();
          if(event.error!=='aborted')this.onError('The microphone or speech service is unavailable. Please type instead.');
        };
        recognition.onend=()=>{if(current()){this.recognition=null;this.onListening(false);}};
        this.onListening(true);recognition.start();return true;
      } catch(_) {
        this.stopListening();this.onError('The microphone or speech service is unavailable. Please type instead.');return false;
      }
    }
    speak(text,language='en') {
      if(typeof text!=='string'||!text.trim())return false;
      if(!this.env.speechSynthesis||!this.env.SpeechSynthesisUtterance)return false;
      this.cancel();
      const utterance=new this.env.SpeechSynthesisUtterance(text.replace(/https?:\/\/\S+/g,''));
      utterance.lang=language==='cs'?'cs-CZ':'en-US';
      const generation=this.generation;
      utterance.onerror=()=>{
        if(generation===this.generation)this.onError('Speech output is unavailable. The reply remains visible.');
      };
      try {this.env.speechSynthesis.speak(utterance);return true;}
      catch(_) {this.onError('Speech output is unavailable. The reply remains visible.');return false;}
    }
  }
  root.BrowserVoice=BrowserVoice;
  if(typeof module!=='undefined')module.exports={BrowserVoice};
})(typeof window==='undefined'?globalThis:window);
