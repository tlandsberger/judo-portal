import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { MyMemberResponse } from '../../api/api-types';
import { MyMemberPage } from './my-member';

describe('MyMemberPage', () => {
  let http: HttpTestingController;

  async function render() {
    await TestBed.configureTestingModule({
      imports: [MyMemberPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(MyMemberPage);
    fixture.componentRef.setInput('id', 'm-1');
    TestBed.tick();
    return fixture;
  }

  afterEach(() => http.verify());

  it('zeigt die Daten nur lesend', async () => {
    const fixture = await render();
    const entry: MyMemberResponse = {
      relation: 'guardian',
      member: {
        id: 'm-1',
        firstName: 'Emma',
        lastName: 'Muster',
        birthDate: '2017-06-01',
        gender: 'female',
        city: 'Wedel',
        membershipType: 'active',
        entryDate: '2023-09-01',
        left: false,
        version: 2,
      },
    };
    http.expectOne('/api/me/members/m-1').flush(entry);
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Emma Muster');
    expect(element.textContent).toContain('01.06.2017');
    expect(element.textContent).toContain('weiblich');
    expect(element.textContent).toContain('Änderungen bitte an die Abteilungsleitung');
    expect(element.querySelector('input, form')).toBeNull();
  });

  it('meldet fremde Mitglieder als nicht sichtbar', async () => {
    const fixture = await render();
    http.expectOne('/api/me/members/m-1').flush(null, { status: 404, statusText: 'Not Found' });
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('nicht sehen');
  });
});
