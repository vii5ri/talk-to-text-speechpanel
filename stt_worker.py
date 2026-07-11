#!/usr/bin/env python3
"""
Hidden pywebview subprocess — Web Speech API real-time STT.
Communicates with parent via JSON lines on stdin/stdout.
  stdin  ← {"action":"start","lang":"th-TH"} | {"action":"stop"} | {"action":"quit"}
  stdout → {"type":"interim","text":"..."} | {"type":"final","text":"..."} | {"type":"end"} | {"type":"ready"}
"""
import sys, json, threading
import webview

STT_HTML = """<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>
<script>
var recog = null;
function init() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { send({type:'error',text:'SpeechRecognition not supported'}); return; }
    recog = new SR();
    recog.continuous = true;
    recog.interimResults = true;
    recog.maxAlternatives = 1;
    recog.onresult = function(e) {
        var interim = '', final_t = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {
            var t = e.results[i][0].transcript;
            if (e.results[i].isFinal) final_t += t;
            else interim += t;
        }
        if (interim) send({type:'interim', text:interim});
        if (final_t) send({type:'final', text:final_t});
    };
    recog.onerror = function(e) { send({type:'error', text:e.error}); };
    recog.onend   = function()  { send({type:'end'}); };
}
function send(obj) {
    if (window.pywebview && window.pywebview.api)
        window.pywebview.api.on_data(JSON.stringify(obj));
}
function start(lang) {
    if (!recog) init();
    recog.lang = lang || 'th-TH';
    try { recog.start(); } catch(e) {}
}
function stop() { if (recog) try { recog.stop(); } catch(e) {} }
</script></body></html>"""


class Api:
    def on_data(self, s):
        print(s, flush=True)


def main():
    api = Api()
    win = webview.create_window(
        'STT-Worker', html=STT_HTML, js_api=api,
        width=1, height=1, x=-9999, y=-9999, frameless=True)

    def read_stdin():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                act = cmd.get('action')
                if act == 'start':
                    win.evaluate_js(f"start('{cmd.get('lang','th-TH')}')")
                elif act == 'stop':
                    win.evaluate_js('stop()')
                elif act == 'quit':
                    break
            except Exception as e:
                print(json.dumps({'type': 'error', 'text': str(e)}), flush=True)

    def on_loaded():
        # Signal parent that webview is ready
        print(json.dumps({'type': 'ready'}), flush=True)

    win.events.loaded += on_loaded
    threading.Thread(target=read_stdin, daemon=True).start()
    webview.start(debug=False)


if __name__ == '__main__':
    main()
