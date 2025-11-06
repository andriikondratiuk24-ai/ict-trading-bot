#!/usr/bin/env python3
"""
Quick demonstration script to show the backtest results summary
"""

import json

print("\n" + "="*80)
print("ICT TRADING BOT - BACKTEST RESULTS FOR AUGUST 2024")
print("="*80 + "\n")

# Load the summary
with open('backtest_summary.json', 'r') as f:
    summary = json.load(f)

print("📊 QUICK SUMMARY\n")
print(f"   Total Trading Signals: {summary['total_signals']:,}")
print(f"   Period: {summary['date_range']}")
print(f"   Most Active Day: {summary['most_active_day']}")

print("\n   Direction Breakdown:")
for direction, count in summary['signals_by_direction'].items():
    percentage = (count / summary['total_signals']) * 100
    print(f"      • {direction}: {count:,} ({percentage:.1f}%)")

print("\n   Session Distribution:")
for session, count in sorted(summary['signals_by_session'].items(), key=lambda x: x[1], reverse=True):
    percentage = (count / summary['total_signals']) * 100
    print(f"      • {session.capitalize()}: {count:,} ({percentage:.1f}%)")

print("\n   Key Conditions:")
for condition, count in sorted(summary['conditions_frequency'].items(), key=lambda x: x[1], reverse=True):
    percentage = (count / summary['total_signals']) * 100
    print(f"      • {condition}: {count:,} ({percentage:.1f}%)")

print("\n" + "="*80)
print("✅ Backtest completed successfully!")
print("   See BACKTEST_RESULTS.md for detailed analysis")
print("   Run 'python3 analyze_signals.py' for full report")
print("="*80 + "\n")
