import React from 'react';
import PropTypes from 'prop-types';
import {
  Col,
  Row,
  Container,
  Button,
  UncontrolledDropdown,
  DropdownToggle,
} from 'reactstrap';

import SimpleTooltip from '../shared/SimpleTooltip';
import DropdownMenuItems from '../shared/DropdownMenuItems';

import InputFilter from './InputFilter';

const FilterControls = ({
  dropdownOptions,
  filterOptions,
  updateFilterText,
  updateFilter,
  dropdownCol,
}) => {
  const createButton = filter => (
    <Button
      color="info"
      outline
      onClick={() => updateFilter(filter.stateName)}
      active={filter.state}
    >
      {filter.text}
    </Button>
  );

  const createDropdowns = colClass => (
    <React.Fragment>
      {dropdownOptions.map(dropdown => (
        <Col sm="auto" className={colClass} key={dropdown.selectedItem}>
          <UncontrolledDropdown className="mr-0 text-nowrap">
            <DropdownToggle caret>{dropdown.selectedItem}</DropdownToggle>
            <DropdownMenuItems
              options={dropdown.options}
              selectedItem={dropdown.selectedItem}
              updateData={dropdown.updateData}
            />
          </UncontrolledDropdown>
        </Col>
      ))}
    </React.Fragment>
  );

  return (
    <Container fluid className="my-3 px-0">
      {!dropdownCol && dropdownOptions.length > 0 && (
        <Row className="p-3 justify-content-left">
          {createDropdowns('py-0 pl-0 pr-3')}
        </Row>
      )}
      <Row className="pb-3 pl-3 justify-content-left">
        {dropdownCol &&
          dropdownOptions.length > 0 &&
          createDropdowns('py-2 pl-0 pr-3')}

        <Col className="col-3 py-2 pl-0 pr-2">
          <InputFilter updateFilterText={updateFilterText} />
        </Col>

        {filterOptions.length > 0 &&
          filterOptions.map(filter => (
            <Col sm="auto" className="p-2" key={filter.stateName}>
              {filter.tooltipText ? (
                <SimpleTooltip
                  text={createButton(filter)}
                  tooltipText={filter.tooltipText}
                />
              ) : (
                createButton(filter)
              )}
            </Col>
          ))}
      </Row>
    </Container>
  );
};

FilterControls.propTypes = {
  dropdownOptions: PropTypes.arrayOf(PropTypes.shape({})),
  filterOptions: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  updateFilter: PropTypes.func.isRequired,
  updateFilterText: PropTypes.func.isRequired,
  dropdownCol: PropTypes.bool,
};

FilterControls.defaultProps = {
  dropdownOptions: null,
  dropdownCol: false,
};

export default FilterControls;
