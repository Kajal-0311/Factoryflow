from decimal import Decimal, ROUND_HALF_UP

class UnitConverter:
    """
    Central Unit Conversion Utility for FactoryFlow ERP.
    Handles conversions with strict Decimal precision.
    """
    NORM_MAP = {
        'kg': 'kg',
        'kilogram': 'kg',
        'kilograms': 'kg',
        'g': 'g',
        'gram': 'g',
        'grams': 'g',
        'gm': 'g',
        'l': 'litre',
        'litre': 'litre',
        'litres': 'litre',
        'liter': 'litre',
        'liters': 'litre',
        'ml': 'ml',
        'millilitre': 'ml',
        'millilitres': 'ml',
        'pieces': 'pieces',
        'piece': 'pieces',
        'pcs': 'pieces',
        'packets': 'packets',
        'packet': 'packets',
        'cartons': 'cartons',
        'carton': 'cartons',
        'box': 'cartons',
    }

    # Base conversions relative to canonical base unit (kg for mass, litre for volume)
    FACTORS_TO_BASE = {
        # Mass (base: kg)
        'kg': ('mass', Decimal('1.0')),
        'g': ('mass', Decimal('0.001')),
        # Volume (base: litre)
        'litre': ('volume', Decimal('1.0')),
        'ml': ('volume', Decimal('0.001')),
        # Discrete
        'pieces': ('discrete', Decimal('1.0')),
        'packets': ('discrete', Decimal('1.0')),
        'cartons': ('discrete', Decimal('1.0')),
    }

    @classmethod
    def normalize_unit(cls, unit_str):
        if not unit_str:
            return ''
        clean = str(unit_str).strip().lower()
        return cls.NORM_MAP.get(clean, clean)

    @classmethod
    def convert(cls, quantity, from_unit, to_unit, packets_per_carton=Decimal('20')):
        """
        Convert a Decimal quantity from from_unit to to_unit.
        """
        if quantity is None:
            return Decimal('0')
        
        qty = Decimal(str(quantity))
        u_from = cls.normalize_unit(from_unit)
        u_to = cls.normalize_unit(to_unit)

        if u_from == u_to:
            return qty

        # Discrete packaging conversions: cartons <-> packets
        if u_from == 'cartons' and u_to == 'packets':
            return (qty * Decimal(str(packets_per_carton))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        if u_from == 'packets' and u_to == 'cartons':
            return (qty / Decimal(str(packets_per_carton))).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        # Standard mass / volume dimension conversions
        if u_from in cls.FACTORS_TO_BASE and u_to in cls.FACTORS_TO_BASE:
            dim_from, factor_from = cls.FACTORS_TO_BASE[u_from]
            dim_to, factor_to = cls.FACTORS_TO_BASE[u_to]

            if dim_from != dim_to:
                raise ValueError(f"Incompatible unit conversion from dimension '{dim_from}' ({from_unit}) to '{dim_to}' ({to_unit})")

            # Convert to base unit, then to target unit
            val_in_base = qty * factor_from
            result = val_in_base / factor_to
            return result.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        raise ValueError(f"Unsupported unit conversion: from '{from_unit}' to '{to_unit}'")
