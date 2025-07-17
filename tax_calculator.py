def calculate_tax(data):
    # Extract values, convert to float
    gross_salary = float(data.get('gross_salary', 0))
    basic_salary = float(data.get('basic_salary', 0))
    hra_received = float(data.get('hra_received', 0))
    rent_paid = float(data.get('rent_paid', 0))
    deduction_80c = float(data.get('deduction_80c', 0))
    deduction_80d = float(data.get('deduction_80d', 0))
    standard_deduction = float(data.get('standard_deduction', 0))
    professional_tax = float(data.get('professional_tax', 0))
    tds = float(data.get('tds', 0))

    # Old Regime Deductions
    total_deductions_old = (
        standard_deduction + hra_received + professional_tax + deduction_80c + deduction_80d
    )
    taxable_income_old = max(gross_salary - total_deductions_old, 0)

    # Old Regime Slabs
    def old_regime_tax(taxable):
        tax = 0
        if taxable > 250000:
            if taxable <= 500000:
                tax += (taxable - 250000) * 0.05
            elif taxable <= 1000000:
                tax += 250000 * 0.05
                tax += (taxable - 500000) * 0.2
            else:
                tax += 250000 * 0.05
                tax += 500000 * 0.2
                tax += (taxable - 1000000) * 0.3
        return tax

    tax_old = old_regime_tax(taxable_income_old)
    tax_old += tax_old * 0.04  # 4% cess
    tax_old = round(tax_old, 2)

    # New Regime Deductions (only standard deduction)
    taxable_income_new = max(gross_salary - standard_deduction, 0)

    # New Regime Slabs
    def new_regime_tax(taxable):
        tax = 0
        slabs = [
            (300000, 0.0),
            (600000, 0.05),
            (900000, 0.10),
            (1200000, 0.15),
            (1500000, 0.20),
        ]
        prev = 0
        for limit, rate in slabs:
            if taxable > limit:
                tax += (limit - prev) * rate
                prev = limit
            else:
                tax += (taxable - prev) * rate
                return tax
        # Above 15L
        if taxable > 1500000:
            tax += (taxable - 1500000) * 0.3
        return tax

    tax_new = new_regime_tax(taxable_income_new)
    tax_new += tax_new * 0.04  # 4% cess
    tax_new = round(tax_new, 2)

    # Best regime
    if tax_old < tax_new:
        best_regime = 'old'
    else:
        best_regime = 'new'

    return tax_old, tax_new, best_regime 