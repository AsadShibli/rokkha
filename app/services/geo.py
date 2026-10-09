from sqlalchemy import ColumnElement, func

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat_col, lng_col, lat: float, lng: float) -> ColumnElement[float]:
    """Great-circle distance in km as a SQL expression, so Postgres sorts by it.

    Plain Haversine on two float columns is fine at city scale. With many thousands of
    officers this would become a PostGIS geography column + GiST index (KNN `<->` ordering).
    """
    dlat = func.radians(lat_col - lat)
    dlng = func.radians(lng_col - lng)
    a = func.power(func.sin(dlat / 2), 2) + func.cos(func.radians(lat)) * func.cos(
        func.radians(lat_col)
    ) * func.power(func.sin(dlng / 2), 2)
    return 2 * EARTH_RADIUS_KM * func.asin(func.sqrt(a))
