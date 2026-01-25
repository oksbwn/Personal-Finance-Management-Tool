import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/core/theme/app_theme.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/modules/ingestion/services/sms_service.dart';

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
        _webController.setBackgroundColor(AppTheme.background);
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
    
    // Web: Headers trigger CORS XHR. Use Query Param instead.
    // Mobile: Headers work fine for WebView.
    if (kIsWeb) {
      final uri = Uri.parse(config.webUiUrl);
      final newUri = uri.replace(queryParameters: {
        ...uri.queryParameters, 
        if (token != null) 'auth_token': token,
      });
      
      // Try to force mobile user agent on Web
      try {
        _webController.setUserAgent('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36');
      } catch (e) {
        // Ignore if unimplemented
      }
      
      _webController.loadRequest(newUri);
    } else {
      final headers = token != null ? {'Authorization': 'Bearer $token'} : <String, String>{};
      _webController.loadRequest(Uri.parse(config.webUiUrl), headers: headers);
    }
  }

  void _onTabTapped(int index) {
    if (index == 0) {
      // Refresh web on tab switch? Optional.
      // _webController.reload();
    }
    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final scaffold = Scaffold(
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: IndexedStack(
          index: _currentIndex,
          children: [
            // Tab 1: WebView Dashboard
            Stack(
              children: [
                WebViewWidget(controller: _webController),
                if (_isLoadingWeb)
                  const Center(child: CircularProgressIndicator()),
              ],
            ),
            
            // Tab 2: Native Settings / Sync
            _buildNativeSettings(context),
          ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: _onTabTapped,
        backgroundColor: AppTheme.surface,
        selectedItemColor: AppTheme.primary,
        unselectedItemColor: AppTheme.textMuted,
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
    );

    if (kIsWeb) {
      return Center(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 450),
          decoration: BoxDecoration(
            color: AppTheme.background,
            border: Border.symmetric(vertical: BorderSide(color: AppTheme.surfaceLight, width: 1)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.5),
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

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Device Status',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
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

          const SizedBox(height: 32),
          Text(
            'Actions',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
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
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: const BorderSide(color: AppTheme.surfaceLight)),
            tileColor: AppTheme.surface,
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
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: const BorderSide(color: AppTheme.surfaceLight)),
            tileColor: AppTheme.surface,
          ),
          
           const SizedBox(height: 32),
          Text(
            'Configuration',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),

          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.surfaceLight),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Backend: ${config.backendUrl}', style: const TextStyle(color: AppTheme.textMuted)),
                const SizedBox(height: 8),
                Text('Web UI: ${config.webUiUrl}', style: const TextStyle(color: AppTheme.textMuted)),
                const SizedBox(height: 8),
                Text('Device ID: ${auth.deviceId}', style: const TextStyle(color: AppTheme.textMuted, fontSize: 10)),
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

  Widget _buildStatusCard(BuildContext context, {
    required IconData icon, 
    required Color color, 
    required String title, 
    required String subtitle,
    Widget? trailing,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.surfaceLight),
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
                Text(subtitle, style: const TextStyle(color: AppTheme.textMuted, fontSize: 14)),
              ],
            ),
          ),
          if (trailing != null) trailing,
        ],
      ),
    );
  }
}
