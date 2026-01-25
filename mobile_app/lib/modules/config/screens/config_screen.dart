import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/core/theme/app_theme.dart';

class ConfigScreen extends StatefulWidget {
  final VoidCallback? onSaved;
  
  const ConfigScreen({super.key, this.onSaved});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _backendCtrl;
  late TextEditingController _webUiCtrl;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    final config = context.read<AppConfig>();
    _backendCtrl = TextEditingController(text: config.backendUrl);
    _webUiCtrl = TextEditingController(text: config.webUiUrl);
  }

  @override
  void dispose() {
    _backendCtrl.dispose();
    _webUiCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    
    setState(() => _isLoading = true);
    
    await context.read<AppConfig>().setUrls(
      backend: _backendCtrl.text.trim(),
      webUi: _webUiCtrl.text.trim(),
    );
    
    // Simulate brief delay or valid check (optional)
    await Future.delayed(const Duration(milliseconds: 500));
    
    setState(() => _isLoading = false);
    
    if (widget.onSaved != null) {
      widget.onSaved!();
    } else {
      if (mounted) {
         ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Configuration Saved')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('Server Configuration'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
               Icon(
                Icons.settings_ethernet,
                size: 64,
                color: AppTheme.primary,
              ),
              const SizedBox(height: 32),
              
              Text(
                'Connect to WealthFam',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textMain
                ),
                textAlign: TextAlign.center,
              ),
               const SizedBox(height: 8),
              Text(
                'Configure your self-hosted server endpoints.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTheme.textMuted
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 48),

              TextFormField(
                controller: _backendCtrl,
                style: const TextStyle(color: AppTheme.textMain),
                decoration: const InputDecoration(
                  labelText: 'Backend API URL',
                  hintText: 'http://192.168.0.9:8000',
                  prefixIcon: Icon(Icons.api, color: AppTheme.textMuted),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) return 'Required';
                  if (!value.startsWith('http')) return 'Must start with http/https';
                  return null;
                },
              ),
              const SizedBox(height: 24),
              
              TextFormField(
                controller: _webUiCtrl,
                style: const TextStyle(color: AppTheme.textMain),
                decoration: const InputDecoration(
                  labelText: 'Web Dashboard URL',
                  hintText: 'http://192.168.0.9:80',
                  prefixIcon: Icon(Icons.web, color: AppTheme.textMuted),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) return 'Required';
                  if (!value.startsWith('http')) return 'Must start with http/https';
                  return null;
                },
              ),
              
              const SizedBox(height: 48),
              
              ElevatedButton(
                onPressed: _isLoading ? null : _save,
                child: _isLoading 
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) 
                  : const Text('Save Configuration'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
