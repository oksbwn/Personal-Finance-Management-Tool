import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/core/theme/app_theme.dart';
import 'package:mobile_app/modules/auth/screens/login_screen.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/modules/ingestion/services/sms_service.dart';
import 'package:mobile_app/modules/home/screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  final config = AppConfig();
  await config.init();
  
  final auth = AuthService(config);
  await auth.init();

  final sms = SmsService(config, auth);
  await sms.init(); // Request permissions

  runApp(MyApp(config: config, auth: auth, sms: sms));
}

class MyApp extends StatelessWidget {
  final AppConfig config;
  final AuthService auth;
  final SmsService sms;

  const MyApp({super.key, required this.config, required this.auth, required this.sms});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: config),
        ChangeNotifierProvider.value(value: auth),
        ChangeNotifierProvider.value(value: sms),
      ],
      child: Consumer<AuthService>(
        builder: (context, auth, _) {
          return MaterialApp(
            title: 'WealthFam',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.darkTheme, // Force Dark/Midnight Theme
            home: auth.isAuthenticated 
                ? const HomeScreen() 
                : const LoginScreen(),
          );
        },
      ),
    );
  }
}
