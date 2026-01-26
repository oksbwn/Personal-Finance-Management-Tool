import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_app/core/config/app_config.dart';
import 'package:mobile_app/modules/auth/services/auth_service.dart';
import 'package:mobile_app/modules/home/models/fund_models.dart';

class FundsService extends ChangeNotifier {
  final AppConfig _config;
  final AuthService _auth;

  PortfolioSummary? _portfolio;
  bool _isLoading = false;
  String? _error;

  PortfolioSummary? get portfolio => _portfolio;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Filter State
  String? _selectedMemberId;
  String? get selectedMemberId => _selectedMemberId;

  FundsService(this._config, this._auth);

  void setMember(String? memberId) {
    _selectedMemberId = memberId;
    fetchFunds();
  }

  Future<void> fetchFunds() async {
    if (_auth.accessToken == null) return;
    
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final url = Uri.parse('${_config.backendUrl}/api/v1/mobile/funds')
           .replace(queryParameters: {
             if (_selectedMemberId != null) 'member_id': _selectedMemberId,
           });
           
      final response = await http.get(
        url,
        headers: {
          'Authorization': 'Bearer ${_auth.accessToken}',
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        _portfolio = PortfolioSummary.fromJson(jsonDecode(response.body));
        _error = null;
      } else {
        _error = 'Failed to load funds: ${response.statusCode}';
      }
    } catch (e) {
      debugPrint('Funds Error: $e');
      _error = 'Network error: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
