import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:workmanager/workmanager.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

const String updateTaskName = "wealthfam_stats_update";

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    debugPrint("WorkManager: Task started - $task");
    
    try {
      final prefs = await SharedPreferences.getInstance();
      final url = prefs.getString('backend_url');
      final token = prefs.getString('access_token');
      
      if (url == null || token == null) {
        debugPrint("WorkManager: Missing credentials");
        return Future.value(true);
      }

      final response = await http.get(
        Uri.parse('$url/api/v1/finance/mobile-summary'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final today = (data['today_total'] ?? 0.0).toStringAsFixed(0);
        final month = (data['monthly_total'] ?? 0.0).toStringAsFixed(0);
        
        final FlutterLocalNotificationsPlugin notifications = FlutterLocalNotificationsPlugin();
        
        String contentTitle = 'WealthFam';
        String contentText = 'Today: ₹$today  |  Month: ₹$month';
        String bigContentTitle = '💰 Your Spending Summary';
        String bigText = '━━━━━━━━━━━━━━━━━━━━━\n📊 Today\'s Expenses\n₹ $today\n\n📈 This Month\n₹ $month\n━━━━━━━━━━━━━━━━━━━━━';
        
        if (data['latest_transaction'] != null) {
          final latest = data['latest_transaction'];
          final amount = (latest['amount'] ?? 0.0).toStringAsFixed(0);
          final desc = latest['description'] ?? 'Transaction';
          final time = latest['time'] ?? '';
          
          contentText = 'Latest: ₹$amount - $desc';
          bigText = '━━━━━━━━━━━━━━━━━━━━━\n🔔 Latest Transaction\n₹ $amount\n$desc\n🕐 $time\n\n📊 Today\'s Total\n₹ $today\n\n📈 Monthly Total\n₹ $month\n━━━━━━━━━━━━━━━━━━━━━';
        }
        
        await notifications.show(
          999,
          contentTitle,
          contentText,
          NotificationDetails(
            android: AndroidNotificationDetails(
              'wealthfam_persistent',
              'WealthFam Live Tracker',
              channelDescription: 'Real-time expense monitoring',
              importance: Importance.low,
              priority: Priority.high,
              ongoing: true,
              autoCancel: false,
              showWhen: true,
              when: DateTime.now().millisecondsSinceEpoch,
              usesChronometer: false,
              icon: 'ic_stat_rupee',
              largeIcon: const DrawableResourceAndroidBitmap('ic_launcher'),
              color: const Color(0xFF1E88E5), // Material Blue 600
              colorized: true,
              styleInformation: BigTextStyleInformation(
                bigText,
                contentTitle: bigContentTitle,
                summaryText: 'Tap to view details',
                htmlFormatBigText: false,
                htmlFormatContentTitle: false,
                htmlFormatSummaryText: false,
              ),
              category: AndroidNotificationCategory.status,
              visibility: NotificationVisibility.public,
            ),
          ),
        );
        
        debugPrint("WorkManager: Notification updated");
      }
    } catch (e) {
      debugPrint("WorkManager: Error - $e");
    }

    return Future.value(true);
  });
}

class NotificationService {
  final FlutterLocalNotificationsPlugin _notifications = FlutterLocalNotificationsPlugin();
  
  Future<void> init() async {
    debugPrint("NotificationService: Initializing...");
    
    const AndroidInitializationSettings androidSettings = AndroidInitializationSettings('ic_notification');
    const InitializationSettings settings = InitializationSettings(android: androidSettings);
    
    await _notifications.initialize(settings);
    
    // Initialize workmanager
    await Workmanager().initialize(callbackDispatcher, isInDebugMode: true);
    
    debugPrint("NotificationService: Initialized");
  }

  Future<bool> start({required String url, required String token}) async {
    debugPrint("NotificationService: Starting persistent notification");
    
    try {
      // Save credentials to SharedPreferences for background access
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('backend_url', url);
      await prefs.setString('access_token', token);
      
      // Show initial notification
      await _notifications.show(
        999,
        'Wealth Fam Monitoring',
        'Initializing background sync...',
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'wealthfam_persistent',
            'WealthFam Sync',
            channelDescription: 'Live transaction monitoring',
            importance: Importance.low,
            priority: Priority.low,
            ongoing: true,
            autoCancel: false,
            showWhen: false,
          ),
        ),
      );
      
      // Register periodic task - runs every 15 minutes
      await Workmanager().registerPeriodicTask(
        "wealthfam_stats",
        updateTaskName,
        frequency: const Duration(minutes: 15),
        initialDelay: const Duration(seconds: 5),
        constraints: Constraints(
          networkType: NetworkType.connected,
        ),
      );
      
      debugPrint("NotificationService: Started successfully");
      
      // Trigger immediate update to show real data
      Future.delayed(const Duration(seconds: 3), () {
        debugPrint("NotificationService: Triggering immediate update");
        updateNow(url: url, token: token);
      });
      
      return true;
    } catch (e, stack) {
      debugPrint("NotificationService: Error starting - $e");
      debugPrint("Stack: $stack");
      return false;
    }
  }

  Future<void> stop() async {
    debugPrint("NotificationService: Stopping");
    await Workmanager().cancelByUniqueName("wealthfam_stats");
    await _notifications.cancel(999);
  }

  Future<void> updateNow({required String url, required String token}) async {
    debugPrint("NotificationService: updateNow called with url=$url");
    try {
      final response = await http.get(
        Uri.parse('$url/api/v1/finance/mobile-summary'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      debugPrint("NotificationService: Response status=${response.statusCode}");
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        debugPrint("NotificationService: Received data: $data");
        final today = (data['today_total'] ?? 0.0).toStringAsFixed(0);
        final month = (data['monthly_total'] ?? 0.0).toStringAsFixed(0);
        
        String contentTitle = 'WealthFam';
        String contentText = 'Today: ₹$today  |  Month: ₹$month';
        String bigContentTitle = '💰 Your Spending Summary';
        String bigText = '━━━━━━━━━━━━━━━━━━━━━\n📊 Today\'s Expenses\n₹ $today\n\n📈 This Month\n₹ $month\n━━━━━━━━━━━━━━━━━━━━━';
        
        if (data['latest_transaction'] != null) {
          final latest = data['latest_transaction'];
          final amount = (latest['amount'] ?? 0.0).toStringAsFixed(0);
          final desc = latest['description'] ?? 'Transaction';
          final time = latest['time'] ?? '';
          
          contentText = 'Latest: ₹$amount - $desc';
          bigText = '━━━━━━━━━━━━━━━━━━━━━\n🔔 Latest Transaction\n₹ $amount\n$desc\n🕐 $time\n\n📊 Today\'s Total\n₹ $today\n\n📈 Monthly Total\n₹ $month\n━━━━━━━━━━━━━━━━━━━━━';
        }

        await _notifications.show(
          999,
          contentTitle,
          contentText,
          NotificationDetails(
            android: AndroidNotificationDetails(
              'wealthfam_persistent',
              'WealthFam Live Tracker',
              channelDescription: 'Real-time expense monitoring',
              importance: Importance.low,
              priority: Priority.high,
              ongoing: true,
              autoCancel: false,
              showWhen: true,
              when: DateTime.now().millisecondsSinceEpoch,
              usesChronometer: false,
              icon: 'ic_stat_rupee',
              largeIcon: const DrawableResourceAndroidBitmap('ic_launcher'),
              color: const Color(0xFF1E88E5), // Material Blue 600
              colorized: true,
              styleInformation: BigTextStyleInformation(
                bigText,
                contentTitle: bigContentTitle,
                summaryText: 'Tap to view details',
                htmlFormatBigText: false,
                htmlFormatContentTitle: false,
                htmlFormatSummaryText: false,
              ),
              category: AndroidNotificationCategory.status,
              visibility: NotificationVisibility.public,
            ),
          ),
        );
        debugPrint("NotificationService: Notification updated with live data");
      }
    } catch (e) {
      debugPrint("NotificationService: Update failed - $e");
    }
  }
}
