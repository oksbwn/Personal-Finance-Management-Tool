class FundHolding {
  final String schemeCode;
  final String schemeName;
  final double units;
  final double currentValue;
  final double investedValue;
  final double profitLoss;
  final String lastUpdated;

  FundHolding({
    required this.schemeCode,
    required this.schemeName,
    required this.units,
    required this.currentValue,
    required this.investedValue,
    required this.profitLoss,
    required this.lastUpdated,
  });

  factory FundHolding.fromJson(Map<String, dynamic> json) {
    return FundHolding(
      schemeCode: json['scheme_code'],
      schemeName: json['scheme_name'],
      units: (json['units'] as num).toDouble(),
      currentValue: (json['current_value'] as num).toDouble(),
      investedValue: (json['invested_value'] as num).toDouble(),
      profitLoss: (json['profit_loss'] as num).toDouble(),
      lastUpdated: json['last_updated'],
    );
  }
}

class PortfolioSummary {
  final double totalInvested;
  final double totalCurrent;
  final double totalPl;
  final List<FundHolding> holdings;

  PortfolioSummary({
    required this.totalInvested,
    required this.totalCurrent,
    required this.totalPl,
    required this.holdings,
  });

  factory PortfolioSummary.fromJson(Map<String, dynamic> json) {
    return PortfolioSummary(
      totalInvested: (json['total_invested'] as num).toDouble(),
      totalCurrent: (json['total_current'] as num).toDouble(),
      totalPl: (json['total_pl'] as num).toDouble(),
      holdings: (json['holdings'] as List)
          .map((i) => FundHolding.fromJson(i))
          .toList(),
    );
  }
}
