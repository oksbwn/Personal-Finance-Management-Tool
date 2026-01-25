import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AppConfig extends ChangeNotifier {
  static const String keyBackendUrl = 'backend_url';
  static const String keyWebUiUrl = 'web_ui_url';
  
  // Defaults from requirements
  static const String defaultBackendUrl = 'http://192.168.0.9:8000';
  static const String defaultWebUiUrl = 'http://192.168.0.9:80';

  late SharedPreferences _prefs;
  bool _initialized = false;

  String _backendUrl = defaultBackendUrl;
  String _webUiUrl = defaultWebUiUrl;

  String get backendUrl => _backendUrl;
  String get webUiUrl => _webUiUrl;
  bool get isInitialized => _initialized;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _backendUrl = _prefs.getString(keyBackendUrl) ?? defaultBackendUrl;
    _webUiUrl = _prefs.getString(keyWebUiUrl) ?? defaultWebUiUrl;
    _initialized = true;
    notifyListeners();
  }

  Future<void> setUrls({required String backend, required String webUi}) async {
    _backendUrl = backend;
    _webUiUrl = webUi;
    await _prefs.setString(keyBackendUrl, backend);
    await _prefs.setString(keyWebUiUrl, webUi);
    notifyListeners();
  }
}
