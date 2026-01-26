import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/core/theme/app_theme.dart';
import 'package:mobile_app/modules/auth/screens/login_screen.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/modules/ingestion/services/sms_service.dart';
import 'package:mobile_app/modules/auth/services/security_service.dart';
import 'package:mobile_app/modules/auth/components/biometric_gate.dart';
import 'package:mobile_app/modules/home/screens/home_screen.dart';
import 'package:mobile_app/core/services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  final notificationService = NotificationService();
  await notificationService.init();
  
  final config = AppConfig();
  await config.init();
  
  final auth = AuthService(config);
  await auth.init();

  final security = SecurityService();
  await security.init();

  final sms = SmsService(config, auth, notificationService);
  await sms.init(); 

  runApp(MyApp(config: config, auth: auth, sms: sms, security: security));
}

class MyApp extends StatelessWidget {
  final AppConfig config;
  final AuthService auth;
  final SmsService sms;
  final SecurityService security;

  const MyApp({super.key, required this.config, required this.auth, required this.sms, required this.security});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: config),
        ChangeNotifierProvider.value(value: auth),
        ChangeNotifierProvider.value(value: security),
        ChangeNotifierProvider.value(value: sms),
      ],
      child: Consumer<AuthService>(
        builder: (context, auth, _) {
          return MaterialApp(
            title: 'WealthFam',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
            home: auth.isAuthenticated 
                ? BiometricGate(child: const HomeScreen()) 
                : const LoginScreen(),
          );
        },
      ),
    );
  }
}
