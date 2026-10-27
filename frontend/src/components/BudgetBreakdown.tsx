import React from 'react';
import type { BudgetReport, Money } from '../types';
import { HelpCircle, ShieldCheck, DollarSign } from 'lucide-react';

interface BudgetBreakdownProps {
  report: BudgetReport;
  totalCost?: Money | null;
  remainingBudget?: Money | null;
  amountOverBudget?: Money | null;
  currency: string;
}

const formatCurrency = (amount: number | string | undefined | null, curr: string) => {
  if (amount === undefined || amount === null) return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  const sym = curr === 'INR' ? '₹' : curr === 'USD' ? '$' : curr === 'EUR' ? '€' : `${curr} `;
  return `${sym}${num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
};

const CostClassBadge: React.FC<{ costClass: string }> = ({ costClass }) => {
  switch (costClass) {
    case 'verified_provider_price':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
          <ShieldCheck className="w-3 h-3" /> Quoted by Provider
        </span>
      );
    case 'calculated_from_verified_prices':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
          Calculated
        </span>
      );
    case 'user_assumption':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
          User Assumption
        </span>
      );
    case 'estimate':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
          Estimate
        </span>
      );
    case 'unknown':
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-700">
          <HelpCircle className="w-3 h-3" /> Unquoted / Unknown
        </span>
      );
  }
};

export const BudgetBreakdown: React.FC<BudgetBreakdownProps> = ({
  report,
  totalCost,
  remainingBudget,
  amountOverBudget,
  currency,
}) => {
  const budgetLimit = report.budget_limit;

  return (
    <div className="bg-white dark:bg-gray-850 rounded-2xl border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 border-b border-gray-200 dark:border-gray-700">
        <div>
          <h4 className="text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-indigo-500" />
            Transparent Budget Report
          </h4>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Deterministic calculation strictly grounded in verified provider results
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500 dark:text-gray-400">Total Quoted Cost</div>
          <div className="text-xl font-extrabold text-gray-900 dark:text-gray-100">
            {totalCost?.amount ? (
              formatCurrency(totalCost.amount, totalCost.currency || currency)
            ) : report.known_subtotal?.amount ? (
              <div>
                <span className="text-amber-600 dark:text-amber-400 text-sm font-bold block">
                  Known so far: {formatCurrency(report.known_subtotal.amount, report.known_subtotal.currency || currency)}
                </span>
                <span className="text-xs block text-gray-400 font-normal">Price incomplete</span>
              </div>
            ) : (
              <span className="text-amber-500 text-sm font-medium">Price incomplete</span>
            )}
          </div>
        </div>
      </div>

      {/* Target & Balance Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-5">
        <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200/80 dark:border-gray-700/80">
          <div className="text-xs text-gray-500 dark:text-gray-400">Budget Limit</div>
          <div className="text-base font-bold text-gray-900 dark:text-gray-100 mt-1">
            {budgetLimit ? formatCurrency(budgetLimit.amount, budgetLimit.currency) : 'No limit set'}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200/80 dark:border-gray-700/80">
          <div className="text-xs text-gray-500 dark:text-gray-400">Remaining Budget</div>
          <div className={`text-base font-bold mt-1 ${remainingBudget && Number(remainingBudget.amount) > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-500 dark:text-gray-400'}`}>
            {remainingBudget ? (
              formatCurrency(remainingBudget.amount, remainingBudget.currency)
            ) : report.remaining_after_known_costs?.amount ? (
              <span>
                {formatCurrency(report.remaining_after_known_costs.amount, report.remaining_after_known_costs.currency || currency)}
                <span className="text-xs font-normal text-gray-400 block">After known costs</span>
              </span>
            ) : (
              '—'
            )}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200/80 dark:border-gray-700/80">
          <div className="text-xs text-gray-500 dark:text-gray-400">Over Budget</div>
          <div className={`text-base font-bold mt-1 ${amountOverBudget && Number(amountOverBudget.amount) > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-gray-500 dark:text-gray-400'}`}>
            {amountOverBudget && Number(amountOverBudget.amount) > 0 ? `+${formatCurrency(amountOverBudget.amount, amountOverBudget.currency)}` : formatCurrency(0, currency)}
          </div>
        </div>
      </div>

      {report.missing_categories && report.missing_categories.length > 0 && (
        <div className="mb-4 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
          <HelpCircle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <span>
            <strong>Incomplete pricing components:</strong> {report.missing_categories.join(', ')}. Final budget comparison cannot be determined.
          </span>
        </div>
      )}

      {/* Itemized Cost Breakdown Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <th className="py-2.5 px-3">Expense Category</th>
              <th className="py-2.5 px-3">Cost Classification</th>
              <th className="py-2.5 px-3">Details & Basis</th>
              <th className="py-2.5 px-3 text-right">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {report.items.map((item, idx) => (
              <tr key={idx} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/40 transition-colors">
                <td className="py-3 px-3 font-medium text-gray-900 dark:text-gray-100">
                  {item.label}
                </td>
                <td className="py-3 px-3">
                  <CostClassBadge costClass={item.cost_class} />
                </td>
                <td className="py-3 px-3 text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate" title={item.basis}>
                  {item.basis}
                </td>
                <td className="py-3 px-3 text-right font-semibold text-gray-900 dark:text-gray-100 whitespace-nowrap">
                  {item.amount !== undefined && item.amount !== null
                    ? formatCurrency(item.amount, item.currency || currency)
                    : <span className="text-gray-400 font-normal italic">Unquoted</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Explanatory notes */}
      {report.notes && report.notes.length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400 space-y-1">
          {report.notes.map((n, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-indigo-400">•</span>
              <span>{n}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
