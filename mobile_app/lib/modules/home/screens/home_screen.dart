import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/core/theme/app_theme.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/modules/ingestion/services/sms_service.dart';
import 'package:mobile_app/modules/ingestion/screens/sms_management_screen.dart';
import 'package:mobile_app/modules/config/screens/config_screen.dart';
import 'package:mobile_app/modules/auth/services/security_service.dart';
import 'package:mobile_app/core/services/foreground_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  late final WebViewController _webController;
  bool _isLoadingWeb = true;

  @override
  void initState() {
    super.initState();
    final config = context.read<AppConfig>();
    
    _webController = WebViewController();
    
    // Platform-specific config
    if (!kIsWeb) {
      try {
        _webController.setJavaScriptMode(JavaScriptMode.unrestricted);
        // Use a safe default, or handle dynamically if possible. 
        // Initial color remains white for better light-theme start.
        _webController.setBackgroundColor(Colors.transparent);
      } catch (e) {
        debugPrint("WebView config error: $e");
      }
    }

    try {
      _webController.setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (String url) {
             if (mounted) setState(() => _isLoadingWeb = true);
          },
          onPageFinished: (String url) {
             if (mounted) setState(() => _isLoadingWeb = false);
          },
          onWebResourceError: (WebResourceError error) {
             debugPrint("Web Error: ${error.description}");
             if (mounted) setState(() => _isLoadingWeb = false);
          },
        ),
      );
    } catch (e) {
      debugPrint("NavigationDelegate error: $e");
      if (mounted) setState(() => _isLoadingWeb = false);
    }

    if (kIsWeb) {
      // Fallback: Dismiss spinner after 2s if Web hooks fail
      Future.delayed(const Duration(seconds: 2), () {
        if (mounted && _isLoadingWeb) setState(() => _isLoadingWeb = false);
      });
    }
    
    final token = context.read<AuthService>().accessToken;
    
    final uri = Uri.parse(config.webUiUrl);
    final newUri = uri.replace(queryParameters: {
      ...uri.queryParameters, 
      if (token != null) 'auth_token': token,
    });

    if (!kIsWeb) {
      // Try to force mobile user agent
      try {
        _webController.setUserAgent('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36');
      } catch (e) { }
    }
    
    _webController.loadRequest(newUri);
  }

  void _onTabTapped(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    final scaffold = WithForegroundTask(
      child: Scaffold(
        backgroundColor: theme.scaffoldBackgroundColor,
        body: SafeArea(
          child: IndexedStack(
            index: _currentIndex,
            children: [
              // Tab 1: WebView Dashboard
              Container(
                color: theme.brightness == Brightness.dark ? AppTheme.darkBg : Colors.white,
                child: Stack(
                  children: [
                    WebViewWidget(controller: _webController),
                    if (_isLoadingWeb)
                      Center(child: CircularProgressIndicator(color: theme.primaryColor)),
                  ],
                ),
              ),
              
              // Tab 2: Native Settings / Sync
              _buildNativeSettings(context),
            ],
          ),
        ),
        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: _onTabTapped,
          backgroundColor: theme.colorScheme.surface,
          selectedItemColor: theme.primaryColor,
          unselectedItemColor: theme.colorScheme.onSurfaceVariant.withOpacity(0.6),
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_outlined),
              activeIcon: Icon(Icons.dashboard),
              label: 'Dashboard',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.settings_suggest_outlined),
              activeIcon: Icon(Icons.settings_suggest),
              label: 'Sync & Config',
            ),
          ],
        ),
      ),
    );

    if (kIsWeb) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 450),
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor,
            border: Border.symmetric(vertical: BorderSide(color: theme.dividerColor, width: 1)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.2),
                blurRadius: 20,
                offset: const Offset(0, 10),
              )
            ],
          ),
          child: scaffold,
        ),
      );
    }
    
    return scaffold;
  }

  Widget _buildNativeSettings(BuildContext context) {
    final auth = context.watch<AuthService>();
    final config = context.watch<AppConfig>();
    final theme = Theme.of(context);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Device Status',
            style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          
          _buildStatusCard(
            context,
            icon: Icons.check_circle,
            color: AppTheme.success,
            title: 'Authenticated',
            subtitle: 'Logged in as tenant ${auth.isApproved ? "(Approved)" : "(Pending)"}',
          ),
          
          const SizedBox(height: 16),
          
          _buildStatusCard(
            context,
            icon: Icons.sync,
            color: AppTheme.primary,
            title: 'Auto-Sync Active',
            subtitle: 'Listening for SMS...',
            trailing: Switch(
              value: context.watch<SmsService>().isSyncEnabled, 
              onChanged: (v) => context.read<SmsService>().toggleSync(v),
            ), 
          ),
          
          const SizedBox(height: 16),
          _buildSyncHealthCard(context),
          
          const SizedBox(height: 16),
          _buildSecurityToggle(
            context,
            title: 'Persistent Sync',
            subtitle: 'Keep app alive for better reliability',
            value: context.watch<SmsService>().isForegroundServiceEnabled,
            onChanged: (v) async {
              try {
                await context.read<SmsService>().toggleForegroundService(v);
                if (context.mounted) {
                   ScaffoldMessenger.of(context).showSnackBar(
                     SnackBar(content: Text(v ? 'Background Sync Started' : 'Background Sync Stopped'))
                   );
                }
              } catch (e) {
                if (context.mounted) {
                   ScaffoldMessenger.of(context).showSnackBar(
                     SnackBar(
                       content: Text('Operation Failed: $e'), 
                       backgroundColor: AppTheme.danger,
                       duration: const Duration(seconds: 10),
                     )
                   );
                }
              }
            },
          ),

          const SizedBox(height: 32),
          Text(
            'Actions',
            style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          
          ListTile(
            title: const Text('Manual Sync (Last 24h)'),
            leading: const Icon(Icons.restore, color: AppTheme.primary),
            onTap: () async {
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Sync Started...')));
              final count = await context.read<SmsService>().syncLastHours(24);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Sync Complete. Sent: $count')));
              }
            },
          ),
          const SizedBox(height: 12),
          ListTile(
            title: const Text('Clear Cache'),
            leading: const Icon(Icons.delete_outline, color: AppTheme.warning),
            onTap: () async {
               await context.read<SmsService>().clearCache();
               if (context.mounted) {
                 ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cache Cleared')));
               }
            },
          ),
          const SizedBox(height: 12),
          ListTile(
            title: const Text('SMS Management'),
            subtitle: const Text('View and manually push history'),
            leading: const Icon(Icons.history_edu, color: AppTheme.primary),
            onTap: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const SmsManagementScreen()));
            },
          ),
          
           const SizedBox(height: 32),
          Text(
            'Configuration',
            style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: theme.colorScheme.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: theme.dividerColor),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('SERVER SETUP', style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.1)),
                    IconButton(
                      icon: const Icon(Icons.edit, size: 16, color: AppTheme.primary),
                      onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ConfigScreen())),
                      tooltip: 'Edit Configuration',
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _buildConfigItem('Backend', config.backendUrl),
                const SizedBox(height: 8),
                _buildConfigItem('Web UI', config.webUiUrl),
                Divider(height: 32, color: theme.dividerColor),
                Text('APP SECURITY', style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.1)),
                const SizedBox(height: 8),
                _buildSecurityToggle(
                  context,
                  title: 'Biometric Lock',
                  subtitle: 'Require fingerprint/face to open',
                  value: context.watch<SecurityService>().isBiometricEnabled,
                  onChanged: (v) => context.read<SecurityService>().setBiometricEnabled(v),
                ),
                _buildSecurityToggle(
                  context,
                  title: 'Privacy Masking',
                  subtitle: 'Blur app in multitasking view',
                  value: context.watch<SecurityService>().isPrivacyEnabled,
                  onChanged: (v) => context.read<SecurityService>().setPrivacyEnabled(v),
                ),
                Divider(height: 32, color: theme.dividerColor),
                Text('DEVICE IDENTIFIER', style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.1)),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: theme.scaffoldBackgroundColor,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          auth.deviceId ?? 'Not Set',
                          style: TextStyle(color: theme.colorScheme.onSurface, fontSize: 13, fontFamily: 'monospace'),
                        ),
                      ),
                      GestureDetector(
                        onTap: () {
                          Clipboard.setData(ClipboardData(text: auth.deviceId ?? ''));
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Device ID copied to clipboard'), duration: Duration(seconds: 1)));
                        },
                        child: Icon(Icons.copy, size: 18, color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () {
                context.read<AuthService>().logout();
              },
              style: OutlinedButton.styleFrom(
                foregroundColor: AppTheme.danger,
                side: const BorderSide(color: AppTheme.danger),
                padding: const EdgeInsets.all(16),
              ),
              child: const Text('Sign Out'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfigItem(String label, String value) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 70, child: Text('$label:', style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 12))),
        Expanded(child: Text(value, style: TextStyle(color: theme.colorScheme.onSurface, fontSize: 12, overflow: TextOverflow.ellipsis))),
      ],
    );
  }

  Widget _buildStatusCard(BuildContext context, {
    required IconData icon, 
    required Color color, 
    required String title, 
    required String subtitle,
    Widget? trailing,
  }) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                Text(subtitle, style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 14)),
              ],
            ),
          ),
          if (trailing != null) trailing,
        ],
      ),
    );
  }

  Widget _buildSyncHealthCard(BuildContext context) {
    final sms = context.watch<SmsService>();
    final theme = Theme.of(context);
    final lastSyncStr = sms.lastSyncTime != null 
        ? DateFormat('HH:mm').format(sms.lastSyncTime!) 
        : 'Never';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.health_and_safety_outlined, size: 16, color: theme.primaryColor),
              const SizedBox(width: 8),
              const Text('Sync Health', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const Spacer(),
              Text(sms.lastSyncStatus ?? 'Standby', 
                style: TextStyle(
                  color: sms.lastSyncStatus == 'Success' ? AppTheme.success : theme.colorScheme.onSurfaceVariant,
                  fontSize: 12, fontWeight: FontWeight.bold
                )
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildHealthStat('Last Sync', lastSyncStr),
              _buildHealthStat('Today', sms.messagesSyncedToday.toString()),
              _buildHealthStat('Queue', sms.queueCount.toString(), isWarning: sms.queueCount > 0),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHealthStat(String label, String value, {bool isWarning = false}) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 11)),
        Text(value, style: TextStyle(
          fontWeight: FontWeight.bold, 
          fontSize: 16,
          color: isWarning ? AppTheme.warning : theme.colorScheme.onSurface
        )),
      ],
    );
  }

  Widget _buildSecurityToggle(BuildContext context, {
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                Text(subtitle, style: TextStyle(color: theme.colorScheme.onSurfaceVariant, fontSize: 11)),
              ],
            ),
          ),
          Transform.scale(
            scale: 0.8,
            child: Switch(
              value: value,
              onChanged: onChanged,
            ),
          ),
        ],
      ),
    );
  }
}
