import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(SyncTaskHandler());
}

class SyncTaskHandler extends TaskHandler {
  int _eventCount = 0;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    debugPrint("ForegroundTask: onStart called at $timestamp");
    // Return immediately - do NOT await anything here
  }

  @override
  void onRepeatEvent(DateTime timestamp) {
    debugPrint("ForegroundTask: onRepeatEvent #$_eventCount at $timestamp");
    _eventCount++;
    
    // Fire and forget - don't await
    _updateNotificationAsync();
  }

  @override
  Future<void> onDestroy(DateTime timestamp, bool isTimeout) async {
    debugPrint("ForegroundTask: onDestroy at $timestamp");
  }
  
  void _updateNotificationAsync() {
    // Run in the background without blocking
    () async {
      try {
        final url = await FlutterForegroundTask.getData<String>(key: 'backend_url');
        final token = await FlutterForegroundTask.getData<String>(key: 'access_token');
        
        if (url == null || token == null) {
          debugPrint("ForegroundTask: Missing credentials");
          return;
        }

        final response = await http.get(
          Uri.parse('$url/api/v1/finance/metrics'),
          headers: {'Authorization': 'Bearer $token'},
        ).timeout(const Duration(seconds: 10));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final today = (data['today_total'] ?? 0.0).toStringAsFixed(0);
          final month = (data['monthly_total'] ?? 0.0).toStringAsFixed(0);

          await FlutterForegroundTask.updateService(
            notificationTitle: 'WealthFam: Active',
            notificationText: 'Today: ₹$today | Month: ₹$month',
          );
          debugPrint("ForegroundTask: Updated notification");
        }
      } catch (e) {
        debugPrint("ForegroundTask: Update failed: $e");
      }
    }();
  }
}

class ForegroundServiceWrapper {
  static Future<void> init() async {
    debugPrint("ForegroundService: Initializing...");
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'wealthfam_sync_service_v2',
        channelName: 'WealthFam Sync',
        channelDescription: 'Maintains background connection for transaction sync.',
        channelImportance: NotificationChannelImportance.HIGH,
        priority: NotificationPriority.HIGH,
      ),
      iosNotificationOptions: const IOSNotificationOptions(
        showNotification: true,
        playSound: false,
      ),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(600000), // 10 minutes
        autoRunOnBoot: true,
        allowWakeLock: true,
        allowWifiLock: false,
      ),
    );
  }

  static Future<bool> start({required String url, required String token}) async {
    debugPrint("ForegroundService: Start requested");
    
    try {
      // Save credentials first
      await FlutterForegroundTask.saveData(key: 'backend_url', value: url);
      await FlutterForegroundTask.saveData(key: 'access_token', value: token);

      // Check and request permissions
      final NotificationPermission permission = await FlutterForegroundTask.checkNotificationPermission();
      if (permission != NotificationPermission.granted) {
        final NotificationPermission result = await FlutterForegroundTask.requestNotificationPermission();
        if (result != NotificationPermission.granted) {
          debugPrint("ForegroundService: Notification permission denied");
          return false;
        }
      }

      if (!await FlutterForegroundTask.isIgnoringBatteryOptimizations) {
        await FlutterForegroundTask.requestIgnoreBatteryOptimization();
      }

      // If already running, just restart
      if (await FlutterForegroundTask.isRunningService) {
        debugPrint("ForegroundService: Service already running, restarting");
        await FlutterForegroundTask.restartService();
        return true;
      }

      // Start the service
      debugPrint("ForegroundService: Starting new service");
      final ServiceRequestResult result = await FlutterForegroundTask.startService(
        serviceId: 256,
        notificationTitle: 'WealthFam Monitoring',
        notificationText: 'Starting background sync...',
        callback: startCallback,
      );

      if (result is ServiceRequestSuccess) {
        debugPrint("ForegroundService: Service started successfully");
        // Trigger initial update after a moment
        Future.delayed(const Duration(seconds: 3), () {
          _triggerManualUpdate();
        });
        return true;
      } else {
        debugPrint("ForegroundService: Failed to start: $result");
        if (result is ServiceRequestFailure) {
          debugPrint("ForegroundService: Error: ${result.error}");
        }
        return false;
      }
    } catch (e, stack) {
      debugPrint("ForegroundService: Exception during start: $e");
      debugPrint("Stack: $stack");
      return false;
    }
  }

  static Future<void> stop() async {
    debugPrint("ForegroundService: Stopping service");
    await FlutterForegroundTask.stopService();
  }

  static Future<void> openBatterySettings() async {
    await FlutterForegroundTask.openIgnoreBatteryOptimizationSettings();
  }
  
  static void _triggerManualUpdate() {
    () async {
      try {
        final url = await FlutterForegroundTask.getData<String>(key: 'backend_url');
        final token = await FlutterForegroundTask.getData<String>(key: 'access_token');
        
        if (url == null || token == null) return;

        final response = await http.get(
          Uri.parse('$url/api/v1/finance/metrics'),
          headers: {'Authorization': 'Bearer $token'},
        ).timeout(const Duration(seconds: 10));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final today = (data['today_total'] ?? 0.0).toStringAsFixed(0);
          final month = (data['monthly_total'] ?? 0.0).toStringAsFixed(0);

          await FlutterForegroundTask.updateService(
            notificationTitle: 'WealthFam: Active',
            notificationText: 'Today: ₹$today | Month: ₹$month',
          );
          debugPrint("ForegroundService: Initial update complete");
        }
      } catch (e) {
        debugPrint("ForegroundService: Initial update failed: $e");
      }
    }();
  }
}

