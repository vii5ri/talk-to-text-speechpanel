#!/usr/bin/env python3
"""
Hidden pywebview subprocess — Web Speech API real-time STT.
Shows a small window to collect mic permission, then moves off-screen.
  stdin  <- {"action":"start","lang":"th-TH"} | {"action":"stop"} | {"action":"quit"}
  stdout -> {"type":"interim","text":"..."} | {"type":"final","text":"..."} | {"type":"end"} | {"type":"ready"}
"""
import sys, json, threading, socket, http.server
import webview

STT_HTML = b"""<!DOCTYPE html>
<html><head><meta charset='utf-8'>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: #1e293b; color: #e2e8f0;
  font-family: 'Leelawadee UI','Segoe UI',sans-serif;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  height: 100vh; gap: 10px; user-select: none;
}
.icon { font-size: 30px; }
p { font-size: 12px; color: #94a3b8; text-align: center; line-height: 1.7; }
</style>
</head>
<body>
<div class="icon">&#127908;</div>
<p>Speech Panel<br>&#3585;&#3619;&#3640;&#3603;&#3634;&#3629;&#3609;&#3640;&#3597;&#3634;&#3605;&#9;&#3652;&#3617;&#3650;&#3588;&#3619;&#3650;&#3615;&#3609;&#3651;&#3609; popup &#3607;&#3637;&#3656;&#3611;&#3619;&#3634;&#3585;&#3615;</p>
<script>
var recog = null;
var micReady = false;

function requestMic() {
    navigator.mediaDevices.getUserMedia({audio: true})
        .then(function(stream) {
            stream.getTracks().forEach(function(t){ t.stop(); });
            micReady = true;
            window.pywebview.api.on_data(JSON.stringify({type:'ready'}));
        })
        .catch(function(err) {
            window.pywebview.api.on_data(JSON.stringify({type:'error', text:'mic:' + err.name}));
        });
}

function init() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        window.pywebview.api.on_data(JSON.stringify({type:'error', text:'no SpeechRecognition'}));
        return;
    }
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
        if (interim) window.pywebview.api.on_data(JSON.stringify({type:'interim', text:interim}));
        if (final_t)  window.pywebview.api.on_data(JSON.stringify({type:'final',  text:final_t}));
    };
    recog.onerror = function(e) {
        window.pywebview.api.on_data(JSON.stringify({type:'error', text:e.error}));
    };
    recog.onend = function() {
        window.pywebview.api.on_data(JSON.stringify({type:'end'}));
    };
}

function start(lang) {
    if (!micReady) { requestMic(); return; }
    if (!recog) init();
    recog.lang = lang || 'th-TH';
    try { recog.start(); } catch(e) {}
}

function stop() { if (recog) try { recog.stop(); } catch(e) {} }
</script>
</body></html>"""


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _serve(port):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(STT_HTML)))
            self.end_headers()
            self.wfile.write(STT_HTML)
        def log_message(self, *a): pass
    http.server.HTTPServer(('127.0.0.1', port), H).serve_forever()


_win = None


class Api:
    def on_data(self, s):
        global _win
        print(s, flush=True)
        try:
            if json.loads(s).get('type') == 'ready' and _win:
                def _move_offscreen():
                    try:
                        _win.move(-9999, -9999)
                        _win.resize(1, 1)
                    except Exception:
                        pass
                threading.Timer(0.4, _move_offscreen).start()
        except Exception:
            pass


def main():
    global _win
    port = _free_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()

    api = Api()
    # Start visible so the mic permission infobar is accessible
    _win = webview.create_window(
        'Speech Panel', url=f'http://127.0.0.1:{port}/',
        js_api=api,
        width=300, height=130,
        frameless=True, on_top=True)

    def read_stdin():
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                act = cmd.get('action')
                if act == 'start':
                    _win.evaluate_js(f"start('{cmd.get('lang', 'th-TH')}')")
                elif act == 'stop':
                    _win.evaluate_js('stop()')
                elif act == 'quit':
                    break
            except Exception as e:
                print(json.dumps({'type': 'error', 'text': str(e)}), flush=True)

    def on_loaded():
        _win.evaluate_js('requestMic()')

    _win.events.loaded += on_loaded
    threading.Thread(target=read_stdin, daemon=True).start()
    webview.start(debug=False)


if __name__ == '__main__':
    main()
