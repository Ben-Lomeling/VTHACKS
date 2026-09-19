"""All Nessie tests use recorded data or MockTransport, never the network."""
import json
from datetime import date

import httpx
import pytest

from app import nessie
from app.models import TruckProfile


@pytest.fixture
def bank():
    return json.loads((nessie.DATA / 'nessie_fixture.json').read_text())


@pytest.fixture
def profile():
    return TruckProfile.model_validate_json((nessie.DATA / 'profile.json').read_text())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('DEMO_NOW', '2026-09-21T06:00')
    def fail(resources):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(nessie, '_live', fail)


@pytest.mark.parametrize('description,expected', [
    ('DIESEL 112.4 GAL @ 3.920', 112.4), ('diesel 90 gal', 90),
    ('DIESEL 0 GAL', None), ('DIESEL -5 GAL', None), ('fuel receipt', None),
    ('DIESEL 1.2.3 GAL', None), ('DIESEL NaN GAL', None), (None, None),
])
def test_gallons(description, expected):
    assert nessie._gallons(description) == expected


def test_fixture_costs(profile):
    result = nessie.get_costs_from_bank(profile)
    proposed, evidence = result['proposed'], result['evidence']
    assert proposed.fuel_price == pytest.approx(3.92, abs=0.0001)
    assert proposed.variable_cpm == pytest.approx(0.27)
    assert proposed.fixed_monthly == 3315
    assert proposed.cost_source == 'nessie'
    assert result['current'] is profile
    assert evidence == {**evidence, 'fuel_gallons': 4210.5, 'fuel_spend': 16505,
        'maintenance_spend': 8100, 'unparsed_count': 0, 'window_days': 90, 'source': 'fixture'}
    assert set(evidence) == {'fuel_gallons', 'fuel_spend', 'maintenance_spend', 'bills', 'unparsed_count', 'window_days', 'source'}


def test_fallback_and_recovery(monkeypatch, bank, profile):
    assert nessie.get_checking_balance() == 2500
    assert nessie.data_source() == 'fixture'
    assert nessie.STATUS == 'fixture'
    monkeypatch.setattr(nessie, '_live', lambda resources: bank)
    assert nessie.get_checking_balance() == 2500
    assert nessie.data_source() == 'live'
    assert nessie.get_costs_from_bank(profile)['evidence']['source'] == 'live'
    assert nessie.STATUS == 'live'


@pytest.mark.parametrize('bad', [{}, {'account': {'balance': 'NaN'}}, {'account': {'balance': 'invalid'}}])
def test_invalid_live_response_falls_back(monkeypatch, bad):
    monkeypatch.setattr(nessie, '_live', lambda resources: bad)
    assert nessie.get_checking_balance() == 2500
    assert nessie.STATUS == 'fixture'


def test_bills_month_boundary():
    assert nessie.get_upcoming_bills() == [
        {'payee': 'Truck payment', 'amount': 2150, 'due_date': date(2026, 9, 22)},
        {'payee': 'Truck insurance', 'amount': 1100, 'due_date': date(2026, 10, 5)},
        {'payee': 'ELD / phone', 'amount': 65, 'due_date': date(2026, 10, 15)},
        {'payee': 'Truck payment', 'amount': 2150, 'due_date': date(2026, 10, 22)},
        {'payee': 'Truck insurance', 'amount': 1100, 'due_date': date(2026, 11, 5)},
    ]


def test_bill_clamp_alias_and_one_off():
    bills = [
        {'payee': 'Truck Finance Co', 'payment_amount': 2150, 'status': 'recurring', 'recurring_date': 31, 'payment_date': '2026-01-31'},
        {'payee': 'one off', 'payment_amount': 10, 'status': 'pending', 'payment_date': '2026-02-01'},
        {'payee': 'cancelled', 'payment_amount': 100, 'status': 'cancelled'},
    ]
    result = nessie._expand(bills, date(2026, 1, 31), 28)
    assert [b['due_date'] for b in result] == [date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 28)]
    assert result[0]['payee'] == 'Truck payment'
    assert nessie._expand(bills, date(2026, 1, 30), 0) == []
    assert nessie._expand(bills, date(2026, 1, 31), -1) == []


def test_bill_start_and_invalid_day():
    bill = {'payee': 'future', 'payment_amount': 10, 'status': 'recurring', 'recurring_date': 5, 'payment_date': '2026-12-05'}
    assert nessie._expand([bill], date(2026, 9, 21), 45) == []
    with pytest.raises(ValueError):
        nessie._expand([{**bill, 'recurring_date': 0}], date(2026, 9, 21), 45)


def test_app_clock(monkeypatch):
    monkeypatch.setenv('DEMO_NOW', '2026-10-05T23:15')
    assert nessie.get_upcoming_bills(0) == [{'payee': 'Truck insurance', 'amount': 1100, 'due_date': date(2026, 10, 5)}]
    monkeypatch.setenv('DEMO_NOW', '')
    assert nessie._today() == date.today()


def test_skip_bad_fuel_and_filter_window(bank, profile):
    fuel = next(p for p in bank['purchases'] if p['description'].startswith('DIESEL'))
    bank['purchases'] = [
        {**fuel, 'purchase_date': '2026-06-23', 'amount': 392, 'description': 'DIESEL 100 GAL'},
        {**fuel, 'purchase_date': '2026-09-20', 'amount': 100, 'description': 'bad'},
        {**fuel, 'purchase_date': '2026-06-22', 'amount': 9999},
        {**fuel, 'purchase_date': '2026-09-21', 'amount': 9999},
        {**fuel, 'purchase_date': '2026-09-20', 'status': 'pending', 'amount': 9999},
    ]
    result = nessie._costs(bank, profile, date(2026, 9, 21))
    assert result['proposed'].fuel_price == 3.92
    assert result['evidence']['unparsed_count'] == 1
    assert result['evidence']['fuel_spend'] == 392
    assert result['evidence']['fuel_gallons'] == 100


def test_missing_gallons_preserve_manual_price(bank, profile):
    bank['purchases'] = []
    assert nessie._costs(bank, profile, date(2026, 9, 21))['proposed'].fuel_price == profile.fuel_price


def test_array_categories_and_scaled_miles(bank, profile):
    for merchant in bank['merchants']:
        merchant['category'] = [merchant['category']]
    proposed = nessie._costs(bank, profile.model_copy(update={'miles_per_month': 20000}), date(2026, 9, 21))['proposed']
    assert proposed.variable_cpm == 0.135


def test_bad_live_costs_use_entire_fixture(monkeypatch, bank, profile):
    bank['purchases'][0]['merchant_id'] = 'missing'
    monkeypatch.setattr(nessie, '_live', lambda resources: bank)
    assert nessie.get_costs_from_bank(profile)['proposed'].variable_cpm == 0.27
    assert nessie.STATUS == 'fixture'


def test_client_endpoints_timeout_and_secret(monkeypatch, tmp_path, bank):
    # Exercise the actual live reader with an in-memory HTTP transport.
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('isolated_nessie', nessie.__file__)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / 'nessie_ids.json').write_text(json.dumps({'account_id': bank['account']['_id']}))
    monkeypatch.setattr(module, 'DATA', tmp_path)
    monkeypatch.setattr(module, 'dotenv_values', lambda path: {'NESSIE_API_KEY': 'test-key'})
    seen = []
    def handler(request):
        assert request.url.params['key'] == 'test-key'
        assert request.extensions['timeout']['read'] == 5
        path = request.url.path
        seen.append(path)
        if path.startswith('/merchants/'):
            return httpx.Response(200, json=next(m for m in bank['merchants'] if path.endswith(m['_id'])))
        resource = path.rsplit('/', 1)[-1]
        return httpx.Response(200, json=bank.get(resource, bank['account']))
    original = httpx.Client
    monkeypatch.setattr(module.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    result = module._live(('account', 'purchases', 'merchants', 'bills', 'deposits'))
    assert result['account']['balance'] == 2500
    assert len(result['merchants']) == 6
    assert len(seen) == 10


def test_errors_do_not_log_key(monkeypatch, caplog):
    def fail(resources):
        raise httpx.ConnectError('https://example.test/?key=SECRET')
    monkeypatch.setattr(nessie, '_live', fail)
    with caplog.at_level('INFO'):
        assert nessie.get_checking_balance() == 2500
    assert 'SECRET' not in caplog.text


def _script(name):
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location(name, nessie.ROOT / 'scripts' / f'{name}.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_history_targets():
    module = _script('seed_nessie')
    purchases, deposits = module.history(date(2026, 9, 21))
    assert len(purchases) == 58 and len(deposits) == 15
    assert sum(p['amount'] for p in purchases if p['merchant_index'] < 3) == 16505
    assert sum(p['amount'] for p in purchases if p['merchant_index'] >= 3) == 8100
    assert all(p['amount'] == int(p['amount']) for p in purchases)


def test_seed_refuses_duplicate_before_request(tmp_path):
    module = _script('seed_nessie')
    out = tmp_path / 'ids.json'
    out.write_text('{}')
    with pytest.raises(FileExistsError):
        module.seed(None, date(2026, 9, 21), out)
    assert out.read_text() == '{}'


def test_recorder_atomic_success_and_failure(tmp_path, bank):
    module = _script('record_fixture')
    output = tmp_path / 'fixture.json'
    ids = {'account_id': bank['account']['_id'], 'merchants': {}}
    def handler(request):
        path = request.url.path
        if path.startswith('/merchants/'):
            value = next(m for m in bank['merchants'] if path.endswith(m['_id']))
        else:
            value = bank.get(path.rsplit('/', 1)[-1], bank['account'])
        return httpx.Response(200, json=value)
    with httpx.Client(base_url=module.BASE, transport=httpx.MockTransport(handler)) as client:
        result = module.record(client, ids, output)
    assert json.loads(output.read_text()) == result
    assert result['account'] == bank['account']
    before = output.read_bytes()
    with httpx.Client(base_url=module.BASE, transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        with pytest.raises(RuntimeError):
            module.record(client, ids, output)
    assert output.read_bytes() == before
