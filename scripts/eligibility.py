"""Evaluate verified structured requirements; ambiguous prose needs agent review."""
import math
import re


def evaluate(listing,rules):
    excluded=[];review=[];preferences=[]
    if listing.get('requirements_verified') is not True:return {'decision':'needs_review','reasons':['requirements_unverified'],'preferences':[]}
    requirements=listing.get('requirements',{})
    for key,item in sorted(requirements.items()):
        if not isinstance(item,dict) or item.get('strength') not in {'hard','preference'}:
            review.append('ambiguous_requirement');continue
        is_hard=item['strength']=='hard';reason=None
        if key=='country':
            country=item.get('value');allowed=rules.get('allowed_countries')
            if not isinstance(country,str) or not country:review.append('country_unknown')
            elif allowed and country not in allowed:reason='location_excluded'
        elif key=='experience':
            minimum=item.get('minimum');years=rules.get('experience_years')
            if isinstance(minimum,str) and re.fullmatch(r'\d+\+',minimum):minimum=int(minimum[:-1])
            if type(minimum) not in (int,float) or not math.isfinite(minimum) or minimum<0:review.append('experience_ambiguous')
            elif type(years) not in (int,float) or not math.isfinite(years) or years<0:review.append('experience_fact_unknown')
            elif years<minimum:reason='experience_minimum'
        elif key=='sponsorship':
            available=item.get('available');needed=rules.get('requires_sponsorship')
            if type(available) is not bool or type(needed) is not bool:review.append('sponsorship_unknown')
            elif needed and not available:reason='sponsorship_unavailable'
        else:review.append('unsupported_requirement')
        if reason:(excluded if is_hard else preferences).append(reason)
    return {'decision':'exclude' if excluded else 'needs_review' if review else 'include','reasons':sorted(set(excluded or review or ['eligible'])),'preferences':sorted(set(preferences))}
