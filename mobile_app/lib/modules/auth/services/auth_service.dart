import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/config/app_config.dart';

class AuthService extends ChangeNotifier {
  final AppConfig _config;
  final _storage = const FlutterSecureStorage();
  
  bool _isAuthenticated = false;
  String? _accessToken;
  String? _tenantId;
  String? _deviceId;
  String? _deviceName;
  bool _isApproved = false;

  bool get isAuthenticated => _isAuthenticated;
  bool get isApproved => _isApproved;
  String? get accessToken => _accessToken;
  String? get deviceId => _deviceId;

  AuthService(this._config);

  Future<void> init() async {
    _accessToken = await _storage.read(key: 'access_token');
    _tenantId = await _storage.read(key: 'tenant_id');
    _deviceId = await _storage.read(key: 'device_id');
    _deviceName = await _storage.read(key: 'device_name');
    
    if (_deviceId == null || _deviceName == null) {
      await _initDeviceInfo();
    }

    if (_accessToken != null) {
      // Validate token or just assume logged in for offline startup
      // Better: Check /mobile/status to verify approval if we have a token
      _isAuthenticated = true;
      try {
        await checkStatus();
        _startHeartbeat();
      } catch (e) {
        // If status check fails (offline), we assume okay if we valid token?
        // Or we might need to be careful. For now, let's allow offline entry but restricted.
        // But for V1, let's just mark authenticated. 
        // Real validation happens on API calls.
        debugPrint('Offline or Check Status Failed: $e');
      }
    }
    notifyListeners();
  }

  Future<void> _initDeviceInfo() async {
    final deviceInfo = DeviceInfoPlugin();
    if (kIsWeb) {
      _deviceId = 'web-client-${DateTime.now().millisecondsSinceEpoch}';
      _deviceName = 'Web Client';
    } else if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      _deviceId = androidInfo.id; // Unique ID
      _deviceName = '${androidInfo.brand} ${androidInfo.model}';
    } else if (Platform.isIOS) {
      final iosInfo = await deviceInfo.iosInfo;
      _deviceId = iosInfo.identifierForVendor;
      _deviceName = '${iosInfo.name} ${iosInfo.model}';
    } else if (Platform.isWindows) {
      final winInfo = await deviceInfo.windowsInfo;
      _deviceId = winInfo.deviceId;
      _deviceName = winInfo.computerName;
    } else {
      _deviceId = 'unknown-${DateTime.now().millisecondsSinceEpoch}';
      _deviceName = 'Unknown Device';
    }
    
    // Ensure we always have a device name fallback
    _deviceName ??= 'Mobile Device';
    
    await _storage.write(key: 'device_id', value: _deviceId);
    await _storage.write(key: 'device_name', value: _deviceName);
    debugPrint('Device Info initialized: ID=$_deviceId, Name=$_deviceName');
  }

  Future<void> setDeviceId(String id) async {
    _deviceId = id;
    await _storage.write(key: 'device_id', value: id);
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    if (_deviceId == null) await _initDeviceInfo();

    final url = Uri.parse('${_config.backendUrl}/api/v1/mobile/login');
    
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'password': password,
          'device_id': _deviceId,
          'device_name': _deviceName,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _accessToken = data['access_token'];
        _isApproved = data['device_status']['is_approved'];
        _tenantId = data['device_status']['tenant_id'];

        await _storage.write(key: 'access_token', value: _accessToken);
        await _storage.write(key: 'tenant_id', value: _tenantId);
        
        _isAuthenticated = true;
        _startHeartbeat();
        notifyListeners();
      } else {
        throw Exception('Login Failed: ${response.statusCode} ${response.body}');
      }
    } catch (e) {
      debugPrint('Login Error: $e');
      rethrow;
    }
  }

  Future<void> logout() async {
    _isAuthenticated = false;
    _accessToken = null;
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'tenant_id');
    notifyListeners();
  }

  Future<void> checkStatus() async {
    if (_accessToken == null || _deviceId == null) return;

    final url = Uri.parse('${_config.backendUrl}/api/v1/mobile/status?device_id=$_deviceId');
    try {
      final response = await http.get(
        url,
        headers: {
          'Authorization': 'Bearer $_accessToken',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _isApproved = data['is_approved'];
        notifyListeners();
      } else if (response.statusCode == 401) {
        // Token expired
        await logout();
      }
    } catch (e) {
      // Ignore network errors for heartbeat
      debugPrint('Status check failed: $e');
    }
  }

  // --- Heartbeat Logic ---
  Timer? _heartbeatTimer;

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(minutes: 5), (timer) {
      if (_isAuthenticated && _accessToken != null) {
        sendHeartbeat();
      } else {
        timer.cancel();
      }
    });
  }

  void stopHeartbeat() {
    _heartbeatTimer?.cancel();
  }

  Future<void> sendHeartbeat() async {
    if (_accessToken == null || _deviceId == null) return;

    final url = Uri.parse('${_config.backendUrl}/api/v1/mobile/heartbeat?device_id=$_deviceId');
    try {
      final response = await http.post(
        url,
        headers: {
          'Authorization': 'Bearer $_accessToken',
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        // debugPrint('Heartbeat sent');
        // Update approval status while we are at it?
        final data = jsonDecode(response.body);
        if (_isApproved != data['is_approved']) {
           _isApproved = data['is_approved'];
           notifyListeners();
        }
      }
    } catch (e) {
      debugPrint('Heartbeat failed: $e');
    }
  }
}
