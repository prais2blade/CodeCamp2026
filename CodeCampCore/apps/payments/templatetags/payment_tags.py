from django import template
register = template.Library()

@register.filter
def payment_color(status):
    colors = {
        'paid': 'green',
        'partial': 'orange',
        'pending': 'red'
    }
    return colors.get(status, 'gray')
