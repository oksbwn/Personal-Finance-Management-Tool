import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/config/app_config.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:telephony/telephony.dart';
import 'package:geolocator/geolocator.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';

extension PlatformCheck on TargetPlatform {
  bool get shouldUseTelephony => this == TargetPlatform.android;
}

// Top-level function for background execution
@pragma('vm:entry-point')
void backgroundMessageHandler(SmsMessage message) async {
  // We need to re-initialize dependencies here as it runs in isolate
  // Ideally, use WorkManager or just do a fire-and-forget HTTP call if possible.
  // But we need Config URL. 
  // For V1 complexity, we might skip background logic if complex, but Telephony supports it.
  // We'll try to read SharedPreferences for URL.
  
  if (message.body == null) return;
  debugPrint("Background SMS: ${message.body}");
  // We can't easily access the full AuthService/AppConfig state here without re-init.
  // For now, let's focus on Foreground/App Open listening or assume minimal background logic.
  // The implementation below focuses on the Service class usage in foreground/active state.
}

class SmsService extends ChangeNotifier {
  final AppConfig _config;
  final AuthService _auth;
  final Telephony _telephony = Telephony.instance;
  late SharedPreferences _prefs;

  bool _isSyncEnabled = true;

  bool get isSyncEnabled => _isSyncEnabled;

  SmsService(this._config, this._auth);

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _isSyncEnabled = _prefs.getBool('is_sync_enabled') ?? true;
    
    if (kIsWeb || !defaultTargetPlatform.shouldUseTelephony) {
       debugPrint("SMS features disabled: Not on Android.");
       return;
    }

    final bool? result = await _telephony.requestPhoneAndSmsPermissions;
    if (result == true) {
      _startListening();
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
    if (!_isSyncEnabled) {
       if (kDebugMode) print("Sync disabled by user.");
       return;
    }

    if (message.body == null || message.address == null) return;

    final String hash = _computeHash(message.address!, message.date.toString(), message.body!);
    
    if (_isCached(hash)) {
      if (kDebugMode) print("Skipping cached SMS: $hash");
      return;
    }

    try {
      await _sendToBackend(message.address!, message.body!, message.date ?? DateTime.now().millisecondsSinceEpoch);
      await _cacheHash(hash);
      if (kDebugMode) print("Processed SMS: $hash");
    } catch (e) {
      if (kDebugMode) print("Failed to send SMS: $e");
      // Queue for offline Retry (Step 6 requirement)
      _queueForRetry(message.address!, message.body!, message.date ?? DateTime.now().millisecondsSinceEpoch);
    }
  }

  String _computeHash(String address, String date, String body) {
    final raw = "$address-$date-$body";
    return sha256.convert(utf8.encode(raw)).toString();
  }

  bool _isCached(String hash) {
    return _prefs.containsKey('sms_hash_$hash');
  }

  Future<void> _cacheHash(String hash) async {
    await _prefs.setBool('sms_hash_$hash', true);
  }
  
  Future<void> clearCache() async {
    final keys = _prefs.getKeys().where((k) => k.startsWith('sms_hash_'));
    for (final key in keys) {
      await _prefs.remove(key);
    }
    notifyListeners();
  }

  Future<void> _sendToBackend(String address, String body, int date) async {
    if (!_auth.isAuthenticated || _auth.accessToken == null) {
      throw Exception("Not Authenticated");
    }

    // Get Location if possible
    double? lat;
    double? lng;
    try {
      // Check permission first to avoid error
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.whileInUse || permission == LocationPermission.always) {
        Position position = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.medium);
        lat = position.latitude;
        lng = position.longitude;
      }
    } catch (e) {
      // Ignore location error
    }

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
      throw Exception("Backend Error: ${response.statusCode}");
    }
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
        
        // We re-hash check just in case
        final hash = _computeHash(address, date.toString(), body);
        if (!_isCached(hash)) {
          await _sendToBackend(address, body, date);
           await _cacheHash(hash);
        }
        successCount++;
      } catch (e) {
        remaining.add(itemStr); // Keep in queue if still failing
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

    // Requires READ_SMS permission
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
            } catch (e) {
               _queueForRetry(msg.address!, msg.body!, msg.date ?? 0);
            }
         }
       }
    }
    return sent;
  }
}
