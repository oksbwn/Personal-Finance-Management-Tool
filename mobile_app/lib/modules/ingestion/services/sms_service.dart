import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/config/app_config.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:telephony/telephony.dart';
import 'package:geolocator/geolocator.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/core/services/notification_service.dart';

extension PlatformCheck on TargetPlatform {
  bool get shouldUseTelephony => this == TargetPlatform.android;
}

// Top-level function for background execution
@pragma('vm:entry-point')
void backgroundMessageHandler(SmsMessage message) async {
  if (message.body == null) return;
  debugPrint("Background SMS: ${message.body}");
}

class SmsService extends ChangeNotifier {
  final AppConfig _config;
  final AuthService _auth;
  final NotificationService _notificationService;
  final Telephony _telephony = Telephony.instance;
  late SharedPreferences _prefs;

  bool _isSyncEnabled = true;
  bool _isForegroundServiceEnabled = false;

  // Stats
  DateTime? _lastSyncTime;
  int _messagesSyncedToday = 0;
  String? _lastSyncStatus;

  bool get isSyncEnabled => _isSyncEnabled;
  bool get isForegroundServiceEnabled => _isForegroundServiceEnabled;
  DateTime? get lastSyncTime => _lastSyncTime;
  int get messagesSyncedToday => _messagesSyncedToday;
  String? get lastSyncStatus => _lastSyncStatus;
  int get queueCount => (_prefs.getStringList(keyQueue) ?? []).length;

  SmsService(this._config, this._auth, this._notificationService);

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _isSyncEnabled = _prefs.getBool('is_sync_enabled') ?? true;
    _isForegroundServiceEnabled = _prefs.getBool('fg_service_enabled') ?? false;
    _messagesSyncedToday = _prefs.getInt('msgs_synced_today') ?? 0;
    final lastSyncMs = _prefs.getInt('last_sync_time');
    if (lastSyncMs != null) {
       _lastSyncTime = DateTime.fromMillisecondsSinceEpoch(lastSyncMs);
       final now = DateTime.now();
       if (_lastSyncTime!.day != now.day || _lastSyncTime!.month != now.month || _lastSyncTime!.year != now.year) {
         _messagesSyncedToday = 0;
         _prefs.setInt('msgs_synced_today', 0);
       }
    }
    
    if (kIsWeb || !defaultTargetPlatform.shouldUseTelephony) {
       debugPrint("SMS features disabled: Not on Android.");
       return;
    }

    final bool? result = await _telephony.requestPhoneAndSmsPermissions;
    if (result == true) {
      _startListening();
      if (_isForegroundServiceEnabled && _auth.accessToken != null) {
        _notificationService.start(
          url: _config.backendUrl,
          token: _auth.accessToken!,
        );
      }
    }
  }

  Future<void> toggleSync(bool enabled) async {
    _isSyncEnabled = enabled;
    await _prefs.setBool('is_sync_enabled', enabled);
    notifyListeners();
  }

  void _startListening() {
    _telephony.listenIncomingSms(
      onNewMessage: (SmsMessage message) {
        _handleSms(message);
      },
      onBackgroundMessage: backgroundMessageHandler,
    );
  }

  Future<void> _handleSms(SmsMessage message) async {
    if (message.body == null || message.address == null) return;
    await processSms(message.address!, message.body!, message.date ?? DateTime.now().millisecondsSinceEpoch);
  }

  Future<Map<String, dynamic>> processSms(String address, String body, int date) async {
    if (!_isSyncEnabled) {
       return {'status': 'disabled', 'reason': 'Sync disabled'};
    }

    final String hash = _computeHash(address, date.toString(), body);
    
    if (_isCached(hash)) {
      return {'status': 'cached', 'hash': hash};
    }

    try {
      final res = await _sendToBackend(address, body, date);
      await _cacheHash(hash);
      _updateSyncStats(true);
      return res;
    } catch (e) {
      debugPrint("Failed to send SMS to backend: $e");
      _updateSyncStats(false);
      // Queue for offline Retry (Step 6 requirement)
      _queueForRetry(address, body, date);
      rethrow; // Rethrow for UI to see error if manual
    }
  }

  String computeHash(String address, String date, String body) {
    final raw = "$address-$date-$body";
    return sha256.convert(utf8.encode(raw)).toString();
  }

  String _computeHash(String address, String date, String body) => computeHash(address, date, body);

  bool isCached(String hash) {
    return _prefs.containsKey('sms_hash_$hash');
  }

  bool _isCached(String hash) => isCached(hash);

  Future<void> cacheHash(String hash) async {
    await _prefs.setBool('sms_hash_$hash', true);
  }

  Future<void> _cacheHash(String hash) async => cacheHash(hash);
  
  Future<void> clearCache() async {
    final keys = _prefs.getKeys().where((k) => k.startsWith('sms_hash_'));
    for (final key in keys) {
      await _prefs.remove(key);
    }
    notifyListeners();
  }

  Future<Map<String, dynamic>> _sendToBackend(String address, String body, int date) async {
    if (!_auth.isAuthenticated || _auth.accessToken == null) {
      throw Exception("Not Authenticated");
    }

    // Get Location if possible
    double? lat;
    double? lng;
    try {
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.whileInUse || permission == LocationPermission.always) {
        Position position = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium),
        );
        lat = position.latitude;
        lng = position.longitude;
      }
    } catch (e) { }

    final url = Uri.parse('${_config.backendUrl}/api/v1/ingestion/sms');
    
    final response = await http.post(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${_auth.accessToken}',
      },
      body: jsonEncode({
        'sender': address,
        'message': body,
        'device_id': _auth.deviceId,
        'latitude': lat,
        'longitude': lng,
      }),
    );

    if (response.statusCode != 200 && response.statusCode != 201) {
      final detail = jsonDecode(response.body)['detail'] ?? 'Backend Error';
      throw Exception("$detail (${response.statusCode})");
    }

    return jsonDecode(response.body);
  }

  // --- Offline Queue Logic ---
  static const String keyQueue = 'sms_offline_queue';

  Future<void> _queueForRetry(String address, String body, int date) async {
    final List<String> queue = _prefs.getStringList(keyQueue) ?? [];
    
    final item = {
      'address': address,
      'body': body,
      'date': date,
      'timestamp': DateTime.now().millisecondsSinceEpoch,
    };
    
    queue.add(jsonEncode(item));
    await _prefs.setStringList(keyQueue, queue);
    notifyListeners();
  }

  Future<void> retryQueue() async {
    final List<String> queue = _prefs.getStringList(keyQueue) ?? [];
    if (queue.isEmpty) return;

    final List<String> remaining = [];
    int successCount = 0;

    for (final itemStr in queue) {
      try {
        final item = jsonDecode(itemStr);
        final address = item['address'];
        final body = item['body'];
        final date = item['date'];
        
        final hash = _computeHash(address, date.toString(), body);
        if (!_isCached(hash)) {
          await _sendToBackend(address, body, date);
           await _cacheHash(hash);
        }
        successCount++;
        _updateSyncStats(true);
      } catch (e) {
        remaining.add(itemStr);
      }
    }
    
    await _prefs.setStringList(keyQueue, remaining);
    if (successCount > 0) notifyListeners();
  }
  
  // --- Manual Sync ---
  
  Future<int> syncLastHours(int hours) async {
    if (kIsWeb || !defaultTargetPlatform.shouldUseTelephony) {
       debugPrint("Manual Sync skipped: Not on Android.");
       return 0;
    }

    final messages = await _telephony.getInboxSms(
      columns: [SmsColumn.ADDRESS, SmsColumn.BODY, SmsColumn.DATE],
    );
    
    final cutoff = DateTime.now().subtract(Duration(hours: hours)).millisecondsSinceEpoch;
    
    int sent = 0;
    for (final msg in messages) {
       if (msg.date != null && msg.date! >= cutoff) {
         if (msg.body == null || msg.address == null) continue;
         
         final hash = _computeHash(msg.address!, msg.date.toString(), msg.body!);
         if (!_isCached(hash)) {
            try {
              await _sendToBackend(msg.address!, msg.body!, msg.date ?? 0);
              await _cacheHash(hash);
              sent++;
              _updateSyncStats(true);
            } catch (e) {
               _queueForRetry(msg.address!, msg.body!, msg.date ?? 0);
            }
         }
       }
    }
    return sent;
  }

  Future<List<SmsMessage>> getAllMessages() async {
    if (kIsWeb || !defaultTargetPlatform.shouldUseTelephony) return [];
    try {
      return await _telephony.getInboxSms(
        columns: [SmsColumn.ADDRESS, SmsColumn.BODY, SmsColumn.DATE],
      );
    } catch (e) {
      debugPrint("Error fetching SMS: $e");
      return [];
    }
  }

  Future<Map<String, dynamic>> sendSmsToBackend(String address, String body, int date) async {
    final res = await _sendToBackend(address, body, date);
    final hash = computeHash(address, date.toString(), body);
    await cacheHash(hash);
    _updateSyncStats(true);
    notifyListeners();
    return res;
  }

  void _updateSyncStats(bool success) {
    _lastSyncTime = DateTime.now();
    _prefs.setInt('last_sync_time', _lastSyncTime!.millisecondsSinceEpoch);
    
    if (success) {
      _messagesSyncedToday++;
      _prefs.setInt('msgs_synced_today', _messagesSyncedToday);
      _lastSyncStatus = "Success";
    } else {
      _lastSyncStatus = "Failed";
    }
    notifyListeners();
  }

  Future<void> toggleForegroundService(bool enabled) async {
    _isForegroundServiceEnabled = enabled;
    await _prefs.setBool('fg_service_enabled', enabled);
    
    if (enabled) {
      if (_auth.accessToken != null) {
        final success = await _notificationService.start(
          url: _config.backendUrl,
          token: _auth.accessToken!,
        );
        if (!success) {
          throw Exception("Failed to start notification service");
        }
      }
    } else {
      await _notificationService.stop();
    }
    notifyListeners();
  }
}
