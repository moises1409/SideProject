import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';


@Component({
  selector: 'app-usecases-loader',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './usecases-loader.component.html',
  styleUrl: './usecases-loader.component.css'
})
export class UsecasesLoaderComponent {
  @Input() useCases: { label: string; value: any, id: string }[] = []; // Input to receive the list of components
  selectedComponent: any = null; 

  onUseCaseChange(event: Event) {
    const selectedValue = (event.target as HTMLSelectElement).value;
    this.selectedComponent = this.useCases.find(useCase => useCase.id === selectedValue)?.value;
  }
}
