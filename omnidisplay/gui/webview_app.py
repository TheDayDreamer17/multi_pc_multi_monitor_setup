"""
Modern Native WebView Desktop Window for OmniDisplay.
Uses WKWebView on macOS and Edge WebView2 on Windows via pywebview if installed.
"""

def launch_webview_app(port: int = 5959):
    try:
        import webview
        window = webview.create_window(
            title="OmniDisplay",
            url=f"http://127.0.0.1:{port}",
            width=920,
            height=700,
            min_size=(740, 560),
            background_color="#0d1117"
        )
        webview.start()
        return True
    except ImportError:
        return False
